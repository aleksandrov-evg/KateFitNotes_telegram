from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.Kate_Fit_Notes.api.auth import require_user
from src.Kate_Fit_Notes.settings import ConfigError


def _crm_error_message(result: dict, fallback: str = "Операция CRM не выполнена.") -> str:
    """Берёт безопасное пояснение ошибки из распространённых форматов Twenty."""
    candidates: list[object] = [result.get("message")]
    error = result.get("error")
    if isinstance(error, dict):
        candidates.append(error.get("message"))
    errors = result.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                candidates.append(item.get("message"))
    messages = result.get("messages")
    if isinstance(messages, list):
        candidates.extend(messages)
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()[:500]
    return fallback


@dataclass(frozen=True)
class StudioSettings:
    base_url: str
    api_key: str = field(repr=False)

    def __post_init__(self):
        parsed = urlsplit(self.base_url)
        local = parsed.hostname in {"localhost", "127.0.0.1"} or (parsed.hostname or "").endswith(".lan")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"} or (parsed.scheme != "https" and not (parsed.scheme == "http" and local)):
            raise ConfigError("CRM_BASE_URL должен использовать HTTPS; HTTP разрешён только для локального стенда.")
        if not self.api_key.strip() or any(character.isspace() for character in self.api_key):
            raise ConfigError("CRM_API_KEY должен содержать непустой API-ключ без пробелов.")


def load_studio_settings() -> StudioSettings | None:
    if os.environ.get("CRM_ENABLED", "0").lower() not in {"1", "true"}:
        return None
    base_url = os.environ.get("CRM_BASE_URL", "").strip()
    api_key = os.environ.get("CRM_API_KEY", "").strip()
    if not base_url or not api_key:
        raise ConfigError("Для CRM_ENABLED нужны CRM_BASE_URL и CRM_API_KEY.")
    return StudioSettings(base_url.rstrip("/"), api_key)


class StudioCrm:
    def __init__(self, settings: StudioSettings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)

    def close(self):
        self.client.close()

    def attendance(self, body: dict, *, preview: bool) -> dict:
        trainer_id = body.get("trainerId")
        trainer = None
        assigned_trainer_id = None
        if trainer_id:
            if body.get("existingClassSessionId"):
                session = self.request("GET", f"/rest/classSessions/{body['existingClassSessionId']}").get("data", {}).get("classSession")
                if not isinstance(session, dict) or session.get("id") != body["existingClassSessionId"]:
                    raise HTTPException(502, "CRM не подтвердила выбранное занятие.")
                assigned_trainer_id = session.get("trainerId")
                if assigned_trainer_id and assigned_trainer_id != trainer_id:
                    raise HTTPException(409, "У занятия уже назначен другой тренер. Измените назначение в карточке занятия.")
            trainer = self.request("GET", f"/rest/studioTrainers/{trainer_id}").get("data", {}).get("studioTrainer")
            if not isinstance(trainer, dict) or trainer.get("id") != trainer_id or trainer.get("deletedAt") or not trainer.get("active") and assigned_trainer_id != trainer_id:
                raise HTTPException(409, "Выберите активного тренера из каталога.")
        data = {key: value for key, value in body.items() if key != "trainerId"}
        result = self.command("/studio/attendance/record-past", {**data, "previewOnly": preview})
        if trainer_id and not preview and assigned_trainer_id != trainer_id:
            # Attendance and trainer assignment use separate guarded CRM commands; retain the attendance key on partial success.
            try:
                session_id = result.get("classSessionId")
                if not isinstance(session_id, str) or str(UUID(session_id)) != session_id:
                    raise ValueError("CRM did not confirm the session UUID")
                assignment_key = str(uuid5(NAMESPACE_URL, f"studio-ui-attendance-trainer:{body['idempotencyKey']}:{session_id}:{trainer_id}"))
                self.command("/studio/sessions/assign-trainer", {"classSessionId": session_id, "trainerId": trainer_id, "requestKey": assignment_key})
            except (HTTPException, ValueError) as error:
                raise HTTPException(502, {"code": "ATTENDANCE_TRAINER_UNCONFIRMED", "message": "Посещение сохранено, но назначение тренера не подтверждено. Проверьте занятие и повторяйте только прежний запрос с тем же ключом."}) from error
        return {**result, **({"trainer": {"id": trainer_id, "name": trainer.get("name", "Тренер")}} if trainer else {})}

    def request(self, method: str, path: str, *, body: dict | None = None, params: dict | None = None) -> dict:
        try:
            response = self.client.request(
                method, f"{self.settings.base_url.rstrip('/')}{path}",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json=body, params=params,
                **({"timeout": 65.0} if path in {"/s/studio/sessions/create", "/s/studio/compensation/close"} else {}),
            )
        except httpx.HTTPError as exc:
            message = "Ответ CRM не получен. Повторите загрузку." if method == "GET" or body and body.get("previewOnly") else "Результат неизвестен. Проверьте историю и повторяйте только с прежним ключом операции."
            raise HTTPException(502, message) from exc
        if response.status_code in {401, 403}:
            raise HTTPException(502, "CRM отклонила серверный API-ключ или его права. Проверьте настройки интеграции.")
        try:
            result = response.json()
        except ValueError as exc:
            message = "CRM вернула некорректный ответ." if method == "GET" else "Результат неизвестен. Проверьте историю и повторяйте только с прежним ключом операции."
            raise HTTPException(502, message) from exc
        if not isinstance(result, dict):
            raise HTTPException(502, "CRM вернула некорректный ответ.")
        if response.status_code >= 400:
            status_code = response.status_code if 400 <= response.status_code < 500 else 502
            raise HTTPException(
                status_code,
                {
                    "code": result.get("code", "CRM_ERROR"),
                    "message": _crm_error_message(result),
                },
            )
        return result

    def command(self, path: str, body: dict) -> dict:
        result = self.request("POST", f"/s{path}", body=body)
        if result.get("success") is not True:
            raise HTTPException(
                409,
                {
                    "code": result.get("code", "CRM_ERROR"),
                    "message": _crm_error_message(result),
                },
            )
        return result

    def record_event(self, event: dict) -> None:
        try:
            existing = self.request("GET", f"/rest/studioEvents/{event['id']}").get("data", {}).get("studioEvent")
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            existing = None
        if existing:
            if any(existing.get(key) != event.get(key) for key in ("eventType", "outcome", "idempotencyKey")):
                raise HTTPException(409, "Событие операции требует проверки журнала CRM.")
            if event["outcome"] == "SUCCESS" and existing.get("details") != event.get("details"):
                raise HTTPException(409, "Событие клиента содержит другие данные.")
            return
        result = self.request("POST", "/rest/studioEvents", body={**event, "occurredAt": datetime.now(timezone.utc).isoformat()})
        created = result.get("data", {}).get("createStudioEvent")
        if not isinstance(created, dict) or created.get("id") != event["id"]:
            raise HTTPException(502, "Запись журнала не подтверждена. Повторите с прежним ключом операции.")

    def perform_operation(self, operation: str, body: dict, username: str, action: Callable[[], dict]) -> dict:
        try:
            return action()
        except Exception as exc:
            failure = exc if isinstance(exc, HTTPException) else HTTPException(502, {"code": "API_OPERATION_UNCONFIRMED", "message": "Результат операции API не подтверждён. Проверьте CRM и повторите с прежним ключом."})
            key = str(body.get("idempotencyKey") or body.get("requestKey") or body.get("clientId"))
            details = failure.detail if isinstance(failure.detail, dict) else {"message": str(failure.detail)}
            # Unknown responses may follow committed writes; never describe them as a rollback.
            event = {"id": str(uuid5(NAMESPACE_URL, f"studio-ui-failure:{operation}:{key}")),
                     "name": "Запрос UI не подтверждён" if failure.status_code >= 500 else "Операция UI отклонена",
                     "eventType": "OPERATION_FAILED", "outcome": "FAILURE", "idempotencyKey": key,
                     "bookingId": body.get("bookingId"), "classSessionId": body.get("classSessionId") or body.get("existingClassSessionId"),
                     "membershipId": body.get("membershipId"),
                     "details": json.dumps({"operation": operation, "operator": username, "source": "KATEFIT_UI",
                                            "execution": "UNKNOWN" if failure.status_code >= 500 else "REJECTED",
                                            "status": failure.status_code, "code": details.get("code", "CRM_ERROR"),
                                            "message": details.get("message", "Операция не подтверждена")}, ensure_ascii=False, sort_keys=True)}
            try:
                self.record_event(event)
            except Exception as audit_error:
                raise HTTPException(502, {"code": "AUDIT_UNCONFIRMED", "message": f"{details.get('message', 'Операция не подтверждена')}. Запись журнала также не подтверждена. Проверьте CRM и повторяйте только с прежним ключом."}) from audit_error
            if failure is exc:
                raise
            raise failure from exc

    def list_records(self, resource: str, cursor: str | None = None) -> dict:
        objects = {"clients": "people", "products": "studioProducts", "packages": "studioMemberships", "bookings": "studioBookings", "sessions": "classSessions", "transactions": "membershipTransactions", "events": "studioEvents", "payments": "studioPayments", "expenses": "studioExpenses", "trainers": "studioTrainers", "trainerRates": "trainerPayRates", "trainerAssignments": "trainerRateAssignments", "trainerPayEntries": "trainerPayEntries"}
        object_name = objects[resource]
        params = {"limit": 100, "depth": 0}
        if cursor:
            params["starting_after"] = cursor
        result = self.request("GET", f"/rest/{object_name}", params=params)
        items = result.get("data", {}).get(object_name)
        page_info = result.get("pageInfo", {})
        if not isinstance(items, list) or not isinstance(page_info, dict):
            raise HTTPException(502, "CRM вернула некорректный список.")
        next_cursor = page_info.get("endCursor") if page_info.get("hasNextPage") else None
        if page_info.get("hasNextPage") and (not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor):
            raise HTTPException(502, "CRM вернула некорректную страницу списка.")
        return {"items": items, "next_cursor": next_cursor}

    def expense_write(self, method: str, path: str, body: dict | None = None) -> dict:
        # CRM expense creation has no idempotency key: a lost response must never invite a blind retry.
        try:
            return self.request(method, path, body=body)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise HTTPException(502, {"code": "EXPENSE_OUTCOME_UNKNOWN", "message": "Результат сохранения расхода неизвестен. Проверьте журнал расходов CRM перед повтором; автоматический повтор запрещён."}) from exc
            raise

    def save_expense(self, body: dict) -> dict:
        result = self.expense_write("POST", "/s/studio/expenses/save", body)
        operation = "updateStudioExpense" if body.get("expenseId") else "createStudioExpense"
        record = result.get(operation)
        try:
            expense_id = str(UUID(record["id"])) if isinstance(record, dict) else None
        except (ValueError, TypeError, KeyError):
            expense_id = None
        if not expense_id or body.get("expenseId") and expense_id != body["expenseId"]:
            raise HTTPException(502, {"code": "EXPENSE_OUTCOME_UNKNOWN", "message": "Сохранение расхода не подтверждено. Проверьте журнал расходов CRM перед повтором."})
        return {"id": expense_id}

    def delete_expense(self, expense_id: UUID) -> dict:
        record_id = str(expense_id)
        result = self.request("GET", f"/rest/studioExpenses/{record_id}")
        data = result.get("data")
        record = data.get("studioExpense") if isinstance(data, dict) else None
        if not isinstance(record, dict) or record.get("id") != record_id:
            raise HTTPException(502, "Не удалось проверить расход перед удалением.")
        result = self.expense_write("DELETE", f"/rest/studioExpenses/{record_id}")
        data = result.get("data")
        deleted = data.get("deleteStudioExpense") if isinstance(data, dict) else None
        if not isinstance(deleted, dict) or deleted.get("id") != record_id:
            raise HTTPException(502, {"code": "EXPENSE_OUTCOME_UNKNOWN", "message": "Удаление расхода не подтверждено. Проверьте журнал расходов CRM перед повтором."})
        return {"id": record_id, "deleted": True}

    def rename_person(self, person_id: UUID, person: RenameClientRequest) -> dict:
        name = {"firstName": person.first_name, "lastName": person.last_name}
        payload = {"name": name}
        if person.email is not None:
            current_data = self.request("GET", f"/rest/people/{person_id}").get("data")
            current = current_data.get("person") if isinstance(current_data, dict) else None
            if not isinstance(current, dict) or current.get("id") != str(person_id):
                raise HTTPException(502, "Не удалось проверить контакт перед сохранением email.")
            emails = current.get("emails") or {}
            if not isinstance(emails, dict):
                raise HTTPException(502, "CRM вернула некорректные email контакта.")
            payload["emails"] = {**emails, "primaryEmail": person.email}
        try:
            result = self.request("PATCH", f"/rest/people/{person_id}", body=payload)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise HTTPException(502, "Сохранение контакта не подтверждено. Обновите список клиентов и при необходимости повторите изменение.") from exc
            raise
        data = result.get("data")
        updated = data.get("updatePerson") if isinstance(data, dict) else None
        if not isinstance(updated, dict) or updated.get("id") != str(person_id) or updated.get("name") != name:
            raise HTTPException(502, "Сохранение контакта не подтверждено. Обновите список клиентов и при необходимости повторите изменение.")
        response = {"id": str(person_id), "name": name}
        if person.email is not None:
            emails = updated.get("emails")
            if not isinstance(emails, dict) or emails.get("primaryEmail") != person.email:
                raise HTTPException(502, "Сохранение email не подтверждено. Обновите список клиентов и проверьте карточку.")
            response["emails"] = emails
        return response

    def create_person(self, person: ClientRequest, username: str) -> dict:
        data = person.crm_data()
        event = {"id": str(person.client_id), "name": "Клиент добавлен из UI", "eventType": "CLIENT_CREATED",
                 "outcome": "SUCCESS", "idempotencyKey": str(person.client_id),
                 "details": json.dumps({"personId": str(person.client_id), "source": "KATEFIT_UI", "operator": username}, ensure_ascii=False, sort_keys=True)}
        matches = self.request("GET", "/rest/people", params={"limit": 1, "filter": f"phones.primaryPhoneNumber[eq]:{person.phone}"}).get("data", {}).get("people")
        if not isinstance(matches, list):
            raise HTTPException(502, "Не удалось проверить дубликат клиента.")
        if matches:
            existing = matches[0]
            existing_name = existing.get("name") or {}
            same_person = (
                existing_name.get("firstName") == person.first_name
                and (existing_name.get("lastName") or "") == person.last_name
                and (existing.get("phones") or {}).get("primaryPhoneNumber") == person.phone
                and ((existing.get("emails") or {}).get("primaryEmail") or "") == person.email
            )
            if not same_person:
                raise HTTPException(409, "Клиент с таким телефоном уже есть в CRM. Найдите его в списке.")
            existing_id = existing.get("id")
            if not isinstance(existing_id, str) or not existing_id:
                raise HTTPException(502, "CRM вернула клиента без идентификатора.")
            self.record_event(event)
            return {"id": existing_id, "duplicate": True}
        try:
            result = self.request("POST", "/rest/people", body=data)
        except HTTPException as exc:
            details = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            raise HTTPException(exc.status_code, {**details, "crmPayload": data}) from exc
        created = result.get("data", {}).get("createPerson")
        if not isinstance(created, dict) or not isinstance(created.get("id"), str):
            raise HTTPException(502, "Результат неизвестен. Повторите с прежним ключом клиента.")
        self.record_event(event)
        return {"id": created["id"], "duplicate": False}


class ExpenseMonthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str) -> str:
        date.fromisoformat(value + "-01")
        return value


class ExpenseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expense_id: UUID | None = Field(default=None, alias="expenseId")
    name: str = Field(min_length=1, max_length=200)
    amount_minor: str = Field(alias="amountMinor", pattern=r"^[1-9][0-9]{0,11}$")
    category: Literal["RENT", "TRAINERS", "MARKETING", "FEES", "SUPPLIES", "TAXES", "OTHER"]
    description: str | None = Field(default=None, max_length=5000)
    cost_type: Literal["FIXED", "VARIABLE"] = Field(alias="costType")
    accrual_month: str = Field(alias="accrualMonth", pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    paid_on: str | None = Field(alias="paidOn", pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Укажите название расхода")
        return value.strip()

    @field_validator("accrual_month")
    @classmethod
    def validate_month(cls, value: str) -> str:
        return ExpenseMonthRequest.validate_month(value)

    @field_validator("paid_on")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)
        return value


class ClientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    client_id: UUID = Field(alias="clientId")
    first_name: str = Field(alias="firstName", min_length=1, max_length=100)
    last_name: str = Field(default="", alias="lastName", max_length=100)
    phone: str = Field(min_length=1, max_length=30)
    email: str = Field(default="", max_length=254)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        if re.search(r"[^0-9+() \-]", value):
            raise ValueError("Укажите российский номер телефона")
        digits = re.sub(r"[^0-9]", "", value)
        if len(digits) == 11 and digits[0] in {"7", "8"}:
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("Укажите российский номер телефона")
        return digits

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Укажите корректный email")
        return value

    def crm_data(self) -> dict:
        data = {
            "name": {"firstName": self.first_name, "lastName": self.last_name},
            "phones": {
                "primaryPhoneNumber": self.phone,
                "primaryPhoneCountryCode": "RU",
                "primaryPhoneCallingCode": "+7",
            },
        }
        if self.email:
            data["emails"] = {"primaryEmail": self.email}
        return data


class RenameClientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    first_name: str = Field(alias="firstName", min_length=1, max_length=100)
    last_name: str = Field(alias="lastName", max_length=100)
    email: str | None = Field(default=None, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Передайте email строкой или не передавайте поле")
        return ClientRequest.validate_email(value)


class PackagePaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID = Field(alias="personId")
    product_id: UUID = Field(alias="productId")
    paid_at: datetime = Field(alias="paidAt")
    amount: float = Field(gt=0, allow_inf_nan=False)
    payment_method: Literal["CASH", "SBP", "CARD"] = Field(alias="paymentMethod")
    external_id: str | None = Field(default=None, alias="externalId", max_length=200)
    fiscal_receipt_id: str | None = Field(default=None, alias="fiscalReceiptId", max_length=200)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)

    @field_validator("paid_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Укажите время с часовым поясом")
        return value


class AttendanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID = Field(alias="personId")
    membership_id: UUID = Field(alias="membershipId")
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime = Field(alias="endsAt")
    reason: str = Field(min_length=1, max_length=2000)
    source: Literal["TRAINER", "ATTENDANCE_LOG", "CLIENT", "ADMIN", "OTHER"]
    source_details: str | None = Field(default=None, alias="sourceDetails", max_length=2000)
    existing_class_session_id: UUID | None = Field(default=None, alias="existingClassSessionId")
    trainer_id: UUID | None = Field(default=None, alias="trainerId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Укажите время с часовым поясом")
        return value


class CreateBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID = Field(alias="personId")
    membership_id: UUID = Field(alias="membershipId")
    class_session_id: UUID = Field(alias="classSessionId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)


class SessionParticipantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID = Field(alias="personId")
    membership_id: UUID = Field(alias="membershipId")


class SessionPaymentParticipantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID = Field(alias="personId")
    payment_id: UUID = Field(alias="paymentId")
    product_id: UUID = Field(alias="productId")


class SessionPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    person_id: UUID = Field(alias="personId")
    product_id: UUID = Field(alias="productId")
    session_format: Literal["GROUP_REFORMER", "INTRO_REFORMER", "PERSONAL_EQUIPMENT", "MAT_PILATES", "STRETCHING", "TRX"] = Field(alias="sessionFormat")
    starts_at: datetime = Field(alias="startsAt")
    duration_minutes: int = Field(alias="durationMinutes", ge=1, le=1440, strict=True)
    status: Literal["PLANNED", "COMPLETED"]
    payment_method: Literal["CASH", "SBP", "CARD"] = Field(alias="paymentMethod")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Укажите время с часовым поясом")
        return value


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(default="", max_length=200)
    session_format: Literal["GROUP_REFORMER", "INTRO_REFORMER", "PERSONAL_EQUIPMENT", "SPLIT_EQUIPMENT", "MAT_PILATES", "STRETCHING", "TRX"] = Field(alias="sessionFormat")
    starts_at: datetime = Field(alias="startsAt")
    duration_minutes: int = Field(alias="durationMinutes", ge=1, le=1440, strict=True)
    capacity: int = Field(ge=1, le=100, strict=True)
    status: Literal["PLANNED", "CONFIRMED", "COMPLETED"]
    trainer_id: UUID | None = Field(default=None, alias="trainerId")
    past_confirmed: bool = Field(default=False, alias="pastConfirmed", strict=True)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)
    participants: list[SessionParticipantRequest | SessionPaymentParticipantRequest] = Field(default_factory=list, max_length=100)
    attendance_reason: str = Field(default="", alias="attendanceReason", max_length=2000)

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Укажите время с часовым поясом")
        return value


class CancelBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: UUID = Field(alias="bookingId")
    cancelled_at: datetime = Field(alias="cancelledAt")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)

    @field_validator("cancelled_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Укажите время с часовым поясом")
        return value


router = APIRouter(prefix="/studio")


def get_studio(request: Request) -> StudioCrm:
    studio = request.app.state.studio_crm
    if studio is None:
        raise HTTPException(503, "Подключение CRM пока не настроено.")
    return studio


@router.get("/auth/status")
def status(response: Response, request: Request, username: str = Depends(require_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"configured": request.app.state.studio_crm is not None, "auth_mode": "api_key"}


@router.post("/attendance/preview")
def preview(body: AttendanceRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.attendance(body.model_dump(mode="json", by_alias=True, exclude_none=True), preview=True)


@router.post("/attendance/record-past")
def record_past(body: AttendanceRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True, exclude_none=True)
    return studio.perform_operation("attendance/record-past", data, username, lambda: studio.attendance(data, preview=False))


@router.get("/records/{resource}")
def records(resource: Literal["clients", "products", "packages", "bookings", "sessions", "transactions", "events", "payments", "expenses", "trainers", "trainerRates", "trainerAssignments", "trainerPayEntries"], cursor: str | None = None, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    if cursor and len(cursor) > 2000:
        raise HTTPException(422, "Некорректный курсор.")
    return studio.list_records(resource, cursor)


@router.post("/clients")
def create_client(body: ClientRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True)
    return studio.perform_operation("clients/create", data, username, lambda: studio.create_person(body, username))


@router.patch("/clients/{person_id}")
def rename_client(person_id: UUID, body: RenameClientRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.rename_person(person_id, body)


@router.post("/package-payments/confirm")
def confirm_package_payment(body: PackagePaymentRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True, exclude_none=True)
    return studio.perform_operation("package-payments/confirm", data, username, lambda: studio.command("/studio/package-payments/confirm", data))


@router.post("/bookings/create")
def create_booking(body: CreateBookingRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True)
    return studio.perform_operation("bookings/create", data, username, lambda: studio.command("/studio/bookings/create", data))


@router.post("/sessions/payment")
def create_session_payment(body: SessionPaymentRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True)
    return studio.perform_operation("sessions/payment", data, username, lambda: studio.command("/studio/sessions/payment", data))


@router.post("/sessions/create")
def create_session(body: CreateSessionRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True, exclude_none=True)
    def execute():
        # The deployed CRM creates classes and assigns trainers through separate guarded commands.
        creation = {key: value for key, value in data.items() if key != "trainerId"}
        result = studio.command("/studio/sessions/create", creation)
        if not body.trainer_id:
            return result
        session_id = result.get("classSessionId")
        try:
            if not isinstance(session_id, str) or str(UUID(session_id)) != session_id:
                raise ValueError("CRM did not confirm the session UUID")
            assignment_key = str(uuid5(NAMESPACE_URL, f"studio-ui-session-trainer:{body.idempotency_key}:{session_id}:{body.trainer_id}"))
            studio.command("/studio/sessions/assign-trainer", {"classSessionId": session_id, "trainerId": str(body.trainer_id), "requestKey": assignment_key})
        except (HTTPException, ValueError) as error:
            raise HTTPException(502, {"code": "SESSION_TRAINER_UNCONFIRMED", "message": "Занятие создано, но назначение тренера не подтверждено. Проверьте карточку и повторяйте только прежний запрос; не создавайте новое занятие."}) from error
        return result
    return studio.perform_operation("sessions/create", data, username, execute)


@router.post("/bookings/cancel")
def cancel_booking(body: CancelBookingRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True)
    return studio.perform_operation("bookings/cancel", data, username, lambda: studio.command("/studio/bookings/cancel", data))


@router.post("/expenses/save")
def save_expense(body: ExpenseRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True)
    if data["expenseId"] is None:
        del data["expenseId"]
    return studio.save_expense(data)


@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: UUID, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.delete_expense(expense_id)


@router.post("/expenses/report")
def expense_report(body: ExpenseMonthRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.request("POST", "/s/studio/expenses/report", body=body.model_dump())


@router.post("/bookings/cancel-pay-as-you-go")
def cancel_pay_as_you_go_booking(body: CancelBookingRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True)
    return studio.perform_operation("bookings/cancel-pay-as-you-go", data, username, lambda: studio.command("/studio/bookings/cancel-pay-as-you-go", data))
