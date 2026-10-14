from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.Kate_Fit_Notes.api.auth import require_user
from src.Kate_Fit_Notes.settings import ConfigError


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
        return self.command("/studio/attendance/record-past", {**body, "previewOnly": preview})

    def request(self, method: str, path: str, *, body: dict | None = None, params: dict | None = None) -> dict:
        try:
            response = self.client.request(
                method, f"{self.settings.base_url.rstrip('/')}{path}",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json=body, params=params,
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
            raise HTTPException(status_code, {"code": result.get("code", "CRM_ERROR"), "message": result.get("message", "Операция CRM не выполнена.")})
        return result

    def command(self, path: str, body: dict) -> dict:
        result = self.request("POST", f"/s{path}", body=body)
        if result.get("success") is not True:
            raise HTTPException(409, {"code": result.get("code", "CRM_ERROR"), "message": result.get("message", "Операция CRM не выполнена.")})
        return result

    def list_records(self, resource: str, cursor: str | None = None) -> dict:
        objects = {"clients": "people", "products": "studioProducts", "packages": "studioMemberships", "bookings": "studioBookings", "sessions": "classSessions", "transactions": "membershipTransactions", "events": "studioEvents"}
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

    def create_person(self, person: ClientRequest) -> dict:
        data = person.crm_data()
        # A browser-generated UUID keeps a retry after a lost response from creating another person.
        try:
            existing = self.request("GET", f"/rest/people/{person.client_id}").get("data", {}).get("person")
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            existing = None
        if existing:
            existing_name = existing.get("name") or {}
            if existing_name.get("firstName") != person.first_name or (existing_name.get("lastName") or "") != person.last_name or (existing.get("phones") or {}).get("primaryPhoneNumber") != person.phone or ((existing.get("emails") or {}).get("primaryEmail") or "") != person.email:
                raise HTTPException(409, "Ключ клиента уже использован с другими данными.")
            return {"id": str(person.client_id), "duplicate": True}
        matches = self.request("GET", "/rest/people", params={"limit": 1, "filter": f"phones.primaryPhoneNumber[eq]:{person.phone}"}).get("data", {}).get("people")
        if not isinstance(matches, list):
            raise HTTPException(502, "Не удалось проверить дубликат клиента.")
        if matches:
            raise HTTPException(409, "Клиент с таким телефоном уже есть в CRM. Найдите его в списке.")
        result = self.request("POST", "/rest/people", body={"id": str(person.client_id), **data})
        created = result.get("data", {}).get("createPerson")
        if not isinstance(created, dict) or created.get("id") != str(person.client_id):
            raise HTTPException(502, "Результат неизвестен. Повторите с прежним ключом клиента.")
        return {"id": created["id"], "duplicate": False}


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
        return {"name": {"firstName": self.first_name, "lastName": self.last_name},
                "phones": {"primaryPhoneNumber": self.phone, "primaryPhoneCountryCode": "RU", "primaryPhoneCallingCode": "+7"},
                "emails": {"primaryEmail": self.email}}


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


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    session_format: Literal["GROUP_REFORMER", "INTRO_REFORMER", "PERSONAL_EQUIPMENT", "SPLIT_EQUIPMENT", "MAT_PILATES", "STRETCHING", "TRX"] = Field(alias="sessionFormat")
    starts_at: datetime = Field(alias="startsAt")
    duration_minutes: int = Field(alias="durationMinutes", ge=1, le=1440, strict=True)
    capacity: int = Field(ge=1, le=100, strict=True)
    status: Literal["PLANNED", "CONFIRMED", "COMPLETED"]
    past_confirmed: bool = Field(default=False, alias="pastConfirmed", strict=True)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)

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
    return studio.attendance(body.model_dump(mode="json", by_alias=True, exclude_none=True), preview=False)


@router.get("/records/{resource}")
def records(resource: Literal["clients", "products", "packages", "bookings", "sessions", "transactions", "events"], cursor: str | None = None, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    if cursor and len(cursor) > 2000:
        raise HTTPException(422, "Некорректный курсор.")
    return studio.list_records(resource, cursor)


@router.post("/clients")
def create_client(body: ClientRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.create_person(body)


@router.post("/package-payments/confirm")
def confirm_package_payment(body: PackagePaymentRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.command("/studio/package-payments/confirm", body.model_dump(mode="json", by_alias=True, exclude_none=True))


@router.post("/bookings/create")
def create_booking(body: CreateBookingRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.command("/studio/bookings/create", body.model_dump(mode="json", by_alias=True))


@router.post("/sessions/create")
def create_session(body: CreateSessionRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.command("/studio/sessions/create", body.model_dump(mode="json", by_alias=True))


@router.post("/bookings/cancel")
def cancel_booking(body: CancelBookingRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.command("/studio/bookings/cancel", body.model_dump(mode="json", by_alias=True))
