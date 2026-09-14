"""Сценарии записи: персональный и групповой слот, свободные часы, цена. Без Telegram."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from psycopg2.errors import UniqueViolation

from src.Kate_Fit_Notes.domain import available_slots
from src.Kate_Fit_Notes.repository import KateFitRepository
from src.Kate_Fit_Notes.services.errors import (
    EmptyParticipantsError,
    InvalidTrainTypeError,
    SlotTakenError,
)
from src.Kate_Fit_Notes.services.prepaid import PrepaidService


@dataclass(frozen=True)
class PersonalPriceHint:
    last_prices: list[dict] = field(default_factory=list)
    prepaid_price: Any = None


class BookingService:
    def __init__(self, repo: KateFitRepository):
        self._repo = repo
        self._prepaid = PrepaidService(repo)

    def list_train_types(self, group: bool) -> list[dict]:
        return self._repo.list_all_train(group)

    def list_available_slots(self, session_date: Any) -> list:
        return available_slots(self._repo.select_time_at_data(session_date))

    def suggest_personal_price(self, client_id: Any, type_train_id: Any) -> PersonalPriceHint:
        prepaid_price = self._prepaid.price_for_session(client_id, type_train_id)
        if prepaid_price is not None:
            return PersonalPriceHint(prepaid_price=prepaid_price)
        return PersonalPriceHint(
            last_prices=self._repo.get_last_price_for_train(client_id, type_train_id)
        )

    def remaining_prepaid_sessions(self, client_id: Any, type_train_id: Any) -> int | None:
        return self._prepaid.remaining_sessions(client_id, type_train_id)

    def book_personal(
        self,
        client_id: Any,
        type_train_id: Any,
        session_date: Any,
        session_time: Any,
        price: Any = None,
    ) -> dict:
        train = self._repo.get_train(type_train_id)
        if train is None or train.get("group_train"):
            raise InvalidTrainTypeError("нужен персональный тип тренировки")

        occupied = self._repo.select_time_at_data(session_date)
        if session_time in occupied:
            raise SlotTakenError("слот уже занят")

        prepaid_price = self._prepaid.price_for_session(client_id, type_train_id)
        if price is None and prepaid_price is not None:
            price = prepaid_price
        accounting_id = self._prepaid.package_id_for_session(client_id, type_train_id)
        complete_id = self._prepaid.complete_id_for_session(client_id, type_train_id)

        try:
            self._repo.insert_in_schedule(
                session_date,
                client_id,
                [client_id],
                session_time,
                train.get("rent_debt"),
                train.get("type_train"),
                False,
                price,
                type_train_id,
                complete_id,
                accounting_id,
            )
        except UniqueViolation as exc:
            raise SlotTakenError("слот уже занят") from exc

        return {
            "client": client_id,
            "date": session_date,
            "time": session_time,
            "price": price,
            "type_train_id": type_train_id,
            "accounting_id": accounting_id,
        }

    def book_group(
        self,
        client_ids: Any,
        type_train_id: Any,
        session_date: Any,
        session_time: Any,
        price: Any = None,
    ) -> dict:
        if not client_ids:
            raise EmptyParticipantsError("нужен хотя бы один участник")

        train = self._repo.get_train(type_train_id)
        if train is None or not train.get("group_train"):
            raise InvalidTrainTypeError("нужен групповой тип тренировки")

        occupied = self._repo.select_time_at_data(session_date)
        if session_time in occupied:
            raise SlotTakenError("слот уже занят")

        participants = [int(item) for item in client_ids]
        try:
            self._repo.insert_in_schedule(
                session_date,
                None,
                participants,
                session_time,
                train.get("rent_debt"),
                train.get("type_train"),
                True,
                price,
                type_train_id,
                False,
                None,
            )
        except UniqueViolation as exc:
            raise SlotTakenError("слот уже занят") from exc

        row = self._repo.get_schedule_at(session_date, session_time)
        if row:
            participants = self._repo.get_schedule_participants(row["id"])
        return {
            "client": None,
            "participants": participants,
            "date": session_date,
            "time": session_time,
            "price": price,
            "type_train_id": type_train_id,
        }
