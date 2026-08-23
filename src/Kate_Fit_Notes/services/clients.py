"""Сценарии клиентов: создать, найти, списки. Без Telegram."""

from __future__ import annotations

from psycopg2.errors import UniqueViolation

from src.Kate_Fit_Notes.domain import normalize_phone
from src.Kate_Fit_Notes.repository import KateFitRepository
from src.Kate_Fit_Notes.services.errors import DuplicateClientError, InvalidPhoneError


def _display_name(value: str | None) -> str:
    return "None" if value is None else value


class ClientService:
    def __init__(self, repo: KateFitRepository):
        self._repo = repo

    def create(
        self,
        raw_phone: str | None,
        name: str | None = "None",
        surname: str | None = "None",
    ) -> dict:
        phone = normalize_phone(raw_phone)
        if phone is None:
            raise InvalidPhoneError("неверный формат номера")
        existing = self._repo.search_client(phone)
        if existing:
            raise DuplicateClientError("клиент уже существует")
        display_name = _display_name(name)
        display_surname = _display_name(surname)
        try:
            self._repo.insert_client_data(phone, display_name, display_surname)
        except UniqueViolation as exc:
            raise DuplicateClientError("клиент уже существует") from exc
        return {"phone": phone, "name": display_name, "surname": display_surname}

    def find_by_phone(self, raw_phone: str | None) -> dict | None:
        phone = normalize_phone(raw_phone)
        if phone is None:
            raise InvalidPhoneError("неверный формат номера")
        rows = self._repo.search_client(phone)
        return rows[0] if rows else None

    def list_recent(self, limit: int = 0) -> list[dict]:
        return self._repo.select_last_client(limit)

    def list_all(self) -> list[dict]:
        return self._repo.show_all_clients()
