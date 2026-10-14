from __future__ import annotations

import os
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
        try:
            response = self.client.post(
                f"{self.settings.base_url.rstrip('/')}/s/studio/attendance/record-past",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json={**body, "previewOnly": preview},
            )
        except httpx.HTTPError as exc:
            message = "Ответ CRM не получен. Повторите предпросмотр." if preview else "Результат неизвестен. Проверьте историю и повторяйте только с прежним ключом операции."
            raise HTTPException(502, message) from exc
        if response.status_code in {401, 403}:
            raise HTTPException(502, "CRM отклонила серверный API-ключ или его права. Проверьте настройки интеграции.")
        try:
            result = response.json()
        except ValueError as exc:
            message = "CRM вернула некорректный ответ." if preview else "Результат неизвестен. Проверьте историю и повторяйте только с прежним ключом операции."
            raise HTTPException(502, message) from exc
        if not isinstance(result, dict):
            raise HTTPException(502, "CRM вернула некорректный ответ.")
        if response.status_code >= 400 or result.get("success") is not True:
            status_code = response.status_code if 400 <= response.status_code < 500 else 502
            raise HTTPException(status_code, {"code": result.get("code", "CRM_ERROR"), "message": result.get("message", "Операция CRM не выполнена.")})
        return result


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
