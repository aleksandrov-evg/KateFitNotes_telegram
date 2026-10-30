from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.Kate_Fit_Notes.api.auth import require_user
from src.Kate_Fit_Notes.api.studio import StudioCrm, get_studio

router = APIRouter(prefix="/studio")


class TrainerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    trainer_id: UUID = Field(alias="trainerId")
    name: str = Field(min_length=1, max_length=200)
    active: bool = Field(default=True, strict=True)


class TrainerRateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    rate_id: UUID = Field(alias="rateId")
    name: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1, strict=True)
    amounts_minor: list[str] = Field(alias="amountsMinor", min_length=4, max_length=4)

    @field_validator("amounts_minor")
    @classmethod
    def valid_amounts(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value.isascii() or not value.isdigit() or len(value) > 12 or int(value) * 10000 > 9007199254740991:
                raise ValueError("Укажите четыре неотрицательные суммы в копейках допустимой точности")
        return values


class RatePublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pay_rate_id: UUID = Field(alias="payRateId")


class TrainerAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    assignment_id: UUID = Field(alias="assignmentId")
    trainer_id: UUID = Field(alias="trainerId")
    pay_rate_id: UUID = Field(alias="payRateId")
    valid_from: datetime = Field(alias="validFrom")
    valid_until: datetime | None = Field(default=None, alias="validUntil")

    @field_validator("valid_from", "valid_until")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Укажите часовой пояс")
        return value

    @model_validator(mode="after")
    def valid_period(self):
        if self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("Окончание должно быть позже начала")
        return self


class SessionTrainerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    class_session_id: UUID = Field(alias="classSessionId")
    trainer_id: UUID = Field(alias="trainerId")
    request_key: UUID = Field(alias="requestKey")


class AttendanceCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: UUID = Field(alias="bookingId")
    status: Literal["ATTENDED", "NO_SHOW", "LATE_CANCEL"]


class CompensationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    class_session_id: UUID = Field(alias="classSessionId")
    trainer_id: UUID | None = Field(default=None, alias="trainerId")
    request_key: UUID = Field(alias="requestKey")
    preview_only: bool = Field(default=False, alias="previewOnly", strict=True)
    preview_token: str | None = Field(default=None, alias="previewToken", pattern=r"^[0-9a-f]{64}$")
    previous_entry_id: UUID | None = Field(default=None, alias="previousEntryId")
    reason: str = Field(default="", max_length=2000)
    attendance_corrections: list[AttendanceCorrectionRequest] = Field(default_factory=list, alias="attendanceCorrections", max_length=100)

    @model_validator(mode="after")
    def confirmation_required(self):
        if not self.preview_only and not self.preview_token:
            raise ValueError("Сначала проверьте расчёт и передайте его подтверждение")
        if self.previous_entry_id and not self.reason:
            raise ValueError("Укажите причину исправления")
        if len({row.booking_id for row in self.attendance_corrections}) != len(self.attendance_corrections):
            raise ValueError("Повторная отметка одного участника")
        return self


def _record(studio: StudioCrm, plural: str, singular: str, record_id: str) -> dict | None:
    try:
        record = studio.request("GET", f"/rest/{plural}/{record_id}").get("data", {}).get(singular)
    except HTTPException as error:
        if error.status_code == 404:
            return None
        raise
    if not isinstance(record, dict) or record.get("id") != record_id:
        raise HTTPException(502, "CRM не подтвердила запись справочника.")
    return record


def _save(studio: StudioCrm, plural: str, singular: str, record_id: str, body: dict, existing: dict | None) -> dict:
    # Client-generated UUIDs let a subsequent read find a create whose response was lost.
    result = studio.request("PATCH" if existing else "POST", f"/rest/{plural}/{record_id}" if existing else f"/rest/{plural}", body=body if existing else {"id": record_id, **body})
    operation = ("update" if existing else "create") + singular[0].upper() + singular[1:]
    updated = result.get("data", {}).get(operation)
    if not isinstance(updated, dict) or updated.get("id") != record_id:
        raise HTTPException(502, "Сохранение не подтверждено. Обновите справочник перед повтором.")
    return {"id": record_id}


@router.post("/trainers/save")
def save_trainer(body: TrainerRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    record_id = str(body.trainer_id)
    return _save(studio, "studioTrainers", "studioTrainer", record_id, {"name": body.name, "active": body.active}, _record(studio, "studioTrainers", "studioTrainer", record_id))


@router.post("/trainer-rates/save")
def save_trainer_rate(body: TrainerRateRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    record_id = str(body.rate_id)
    existing = _record(studio, "trainerPayRates", "trainerPayRate", record_id)
    if existing and (existing.get("publishedSnapshot") or existing.get("publishedAt")):
        raise HTTPException(409, "Опубликованный тариф не редактируется. Создайте новую версию.")
    data = {"name": body.name, "version": body.version, "sessionFormat": "GROUP_REFORMER", **{f"amountFor{index}": {"amountMicros": int(value) * 10000, "currencyCode": "RUB"} for index, value in enumerate(body.amounts_minor, 1)}}
    return _save(studio, "trainerPayRates", "trainerPayRate", record_id, data, existing)


@router.post("/trainer-rates/publish")
def publish_trainer_rate(body: RatePublicationRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    return studio.command("/studio/compensation/publish-rate", body.model_dump(mode="json", by_alias=True))


@router.post("/trainer-assignments/save")
def save_trainer_assignment(body: TrainerAssignmentRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    trainer = _record(studio, "studioTrainers", "studioTrainer", str(body.trainer_id))
    rate = _record(studio, "trainerPayRates", "trainerPayRate", str(body.pay_rate_id))
    if not trainer or not trainer.get("active") or not rate or not rate.get("publishedSnapshot"):
        raise HTTPException(409, "Выберите активного тренера и опубликованный тариф.")
    cursor = None
    seen = set()
    while True:
        page = studio.list_records("trainerAssignments", cursor)
        for assignment in page["items"]:
            if assignment.get("deletedAt") or assignment.get("id") == str(body.assignment_id) or assignment.get("trainerId") != str(body.trainer_id):
                continue
            try:
                starts_at = datetime.fromisoformat(assignment["validFrom"].replace("Z", "+00:00"))
                ends_at = datetime.fromisoformat(assignment["validUntil"].replace("Z", "+00:00")) if assignment.get("validUntil") else None
                if starts_at.tzinfo is None or ends_at is not None and ends_at.tzinfo is None:
                    raise ValueError("Missing timezone")
                overlap = (body.valid_until is None or starts_at < body.valid_until) and (ends_at is None or body.valid_from < ends_at)
            except (KeyError, ValueError, TypeError) as error:
                raise HTTPException(409, "Периоды тарифов требуют сверки в CRM.") from error
            if overlap:
                raise HTTPException(409, "Период пересекается с другим тарифом этого тренера. Сначала измените окончание предыдущего периода.")
        cursor = page["next_cursor"]
        if not cursor:
            break
        if cursor in seen or len(seen) >= 100:
            raise HTTPException(502, "Не удалось полностью проверить периоды тарифов.")
        seen.add(cursor)
    data = body.model_dump(mode="json", by_alias=True)
    record_id = data.pop("assignmentId")
    data["name"] = f"{trainer.get('name', 'Тренер')} · {rate.get('name', 'Тариф')}"
    return _save(studio, "trainerRateAssignments", "trainerRateAssignment", record_id, data, _record(studio, "trainerRateAssignments", "trainerRateAssignment", record_id))


@router.post("/sessions/assign-trainer")
def assign_session_trainer(body: SessionTrainerRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True)
    return studio.perform_operation("sessions/assign-trainer", data, username, lambda: studio.command("/studio/sessions/assign-trainer", data))


@router.post("/compensation/close")
def close_compensation(body: CompensationRequest, username: str = Depends(require_user), studio: StudioCrm = Depends(get_studio)):
    data = body.model_dump(mode="json", by_alias=True, exclude_none=True)
    def execute():
        result = studio.command("/studio/compensation/close", data)
        if body.preview_only:
            snapshot = result.get("snapshot")
            valid = result.get("preview") is True and isinstance(snapshot, dict) and isinstance(result.get("previewToken"), str) and len(result["previewToken"]) == 64
        else:
            valid = result.get("preview") is False and isinstance(result.get("entryId"), str) and isinstance(result.get("amountMicros"), int) and not isinstance(result.get("amountMicros"), bool) and 0 <= result["amountMicros"] <= 9007199254740991
        if not valid:
            raise HTTPException(502, "CRM не подтвердила результат начисления. Проверьте журнал и сохраните прежний ключ операции.")
        return result

    if body.preview_only:
        return execute()
    return studio.perform_operation("compensation/close", data, username, execute)
