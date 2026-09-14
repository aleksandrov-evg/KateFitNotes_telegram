"""Пакеты предоплаты: создание и списание занятий. Без Telegram.

Списание только по schedule.accounting_id: used = число занятий
с этим id пакета. Занятия без accounting_id или с чужим пакетом
в used не входят. Два открытых пакета — отказ без записи.
"""

from __future__ import annotations

from typing import Any

from src.Kate_Fit_Notes.domain import price_per_train, should_complete_prepaid
from src.Kate_Fit_Notes.repository import KateFitRepository
from src.Kate_Fit_Notes.services.errors import InvalidPrepaidError, MultiplePrepaidError


def _used_count(row: dict) -> int:
    return int(row.get("count") or 0)


class PrepaidService:
    def __init__(self, repo: KateFitRepository):
        self._repo = repo

    def add_package(
        self,
        client_id: Any,
        type_train_id: Any,
        summ: Any,
        count: Any,
    ) -> dict:
        try:
            count_train = int(count)
        except (TypeError, ValueError) as exc:
            raise InvalidPrepaidError("количество тренировок должно быть числом") from exc
        if count_train <= 0:
            raise InvalidPrepaidError("количество тренировок не может быть 0")

        try:
            summ_value = int(summ)
        except (TypeError, ValueError) as exc:
            raise InvalidPrepaidError("сумма должна быть числом") from exc

        active = self._repo.get_active_prepaid_for_client(client_id, type_train_id)
        if active:
            raise MultiplePrepaidError(len(active), [row["id"] for row in active])

        price = price_per_train(summ_value, count_train)
        self._repo.insert_in_accounting(
            client_id, summ_value, count_train, price, type_train_id
        )
        return {
            "client_id": client_id,
            "type_train_id": type_train_id,
            "summ": summ_value,
            "count_train": count_train,
            "price_per_train": price,
        }

    def price_for_session(self, client_id: Any, type_train_id: Any) -> Any:
        prepaid = self._active(client_id, type_train_id)
        if len(prepaid) == 1:
            return prepaid[0]["price_per_train"]
        return None

    def remaining_sessions(self, client_id: Any, type_train_id: Any) -> int | None:
        prepaid = self._repo.get_active_prepaid_for_client(client_id, type_train_id)
        if len(prepaid) != 1:
            return None
        usage = self._repo.get_count_prepaid_train(client_id, type_train_id)
        if len(usage) != 1:
            return prepaid[0].get("count_train")
        return usage[0]["count_train"] - _used_count(usage[0])

    def package_id_for_session(self, client_id: Any, type_train_id: Any) -> Any:
        prepaid = self._active(client_id, type_train_id)
        if len(prepaid) != 1:
            return None
        return prepaid[0]["id"]

    def complete_id_for_session(self, client_id: Any, type_train_id: Any) -> Any:
        prepaid = self._active(client_id, type_train_id)
        if len(prepaid) != 1:
            return False
        prepaid_row = prepaid[0]
        usage = self._repo.get_count_prepaid_train(client_id, type_train_id)
        used = _used_count(usage[0]) if len(usage) == 1 else 0
        count_train = (
            usage[0]["count_train"] if len(usage) == 1 else prepaid_row["count_train"]
        )
        if should_complete_prepaid(count_train, used):
            return prepaid_row["id"]
        return False

    def _active(self, client_id: Any, type_train_id: Any) -> list[dict]:
        prepaid = self._repo.get_active_prepaid_for_client(client_id, type_train_id)
        if len(prepaid) > 1:
            raise MultiplePrepaidError(len(prepaid), [row["id"] for row in prepaid])
        return prepaid
