"""Сценарии записи: персональный и групповой слот, свободные часы, цена. Без Telegram."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from psycopg2.errors import UniqueViolation

from src.Kate_Fit_Notes.domain import (
    GROUP_CLIENT_ID,
    available_slots,
    format_client_list,
    parse_client_list,
    should_complete_prepaid,
)
from src.Kate_Fit_Notes.repository import KateFitRepository
from src.Kate_Fit_Notes.services.errors import (
    EmptyParticipantsError,
    InvalidTrainTypeError,
    MultiplePrepaidError,
    SlotTakenError,
)


@dataclass(frozen=True)
class PersonalPriceHint:
    last_prices: list[dict] = field(default_factory=list)
    prepaid_price: Any = None


def _used_count(row: dict) -> int:
    return int(row.get("count") or 0)


class BookingService:
    def __init__(self, repo: KateFitRepository):
        self._repo = repo

    def list_available_slots(self, session_date: Any) -> list:
        return available_slots(self._repo.select_time_at_data(session_date))

    def suggest_personal_price(self, client_id: Any, type_train_id: Any) -> PersonalPriceHint:
        prepaid = self._repo.get_active_prepaid_for_client(client_id, type_train_id)
        if len(prepaid) > 1:
            raise MultiplePrepaidError(len(prepaid), [row["id"] for row in prepaid])
        if len(prepaid) == 1:
            return PersonalPriceHint(prepaid_price=prepaid[0]["price_per_train"])
        return PersonalPriceHint(
            last_prices=self._repo.get_last_price_for_train(client_id, type_train_id)
        )

    def remaining_prepaid_sessions(self, client_id: Any, type_train_id: Any) -> int | None:
        prepaid = self._repo.get_active_prepaid_for_client(client_id, type_train_id)
        if len(prepaid) != 1:
            return None
        usage = self._repo.get_count_prepaid_train(client_id, type_train_id)
        if len(usage) != 1:
            return prepaid[0].get("count_train")
        return usage[0]["count_train"] - _used_count(usage[0])

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

        prepaid = self._repo.get_active_prepaid_for_client(client_id, type_train_id)
        if len(prepaid) > 1:
            raise MultiplePrepaidError(len(prepaid), [row["id"] for row in prepaid])
        if price is None and len(prepaid) == 1:
            price = prepaid[0]["price_per_train"]

        complete_id: Any = False
        if len(prepaid) == 1:
            complete_id = self._prepaid_complete_id(client_id, type_train_id, prepaid[0])

        try:
            self._repo.insert_in_schedule(
                session_date,
                client_id,
                format_client_list([client_id]),
                session_time,
                train.get("rent_debt"),
                train.get("type_train"),
                False,
                price,
                type_train_id,
                complete_id,
            )
        except UniqueViolation as exc:
            raise SlotTakenError("слот уже занят") from exc

        return {
            "client": client_id,
            "date": session_date,
            "time": session_time,
            "price": price,
            "type_train_id": type_train_id,
        }

    def _prepaid_complete_id(
        self, client_id: Any, type_train_id: Any, prepaid_row: dict
    ) -> Any:
        usage = self._repo.get_count_prepaid_train(client_id, type_train_id)
        used = _used_count(usage[0]) if len(usage) == 1 else 0
        count_train = usage[0]["count_train"] if len(usage) == 1 else prepaid_row["count_train"]
        if should_complete_prepaid(count_train, used):
            return prepaid_row["id"]
        return False

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

        client_list = format_client_list(client_ids)
        try:
            self._repo.insert_in_schedule(
                session_date,
                GROUP_CLIENT_ID,
                client_list,
                session_time,
                train.get("rent_debt"),
                train.get("type_train"),
                True,
                price,
                type_train_id,
                False,
            )
        except UniqueViolation as exc:
            raise SlotTakenError("слот уже занят") from exc

        row = self._repo.get_schedule_at(session_date, session_time)
        participants = parse_client_list(row["client_list"] if row else client_list)
        return {
            "client": GROUP_CLIENT_ID,
            "participants": participants,
            "date": session_date,
            "time": session_time,
            "price": price,
            "type_train_id": type_train_id,
        }
