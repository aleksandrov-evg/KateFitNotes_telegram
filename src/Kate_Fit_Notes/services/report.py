"""Помесячный отчёт по прибыли. Без Telegram.

Формула: income = sum(price) - sum(rent_debt) по main.schedule
(SQL get_incom_all_month_balance). Персональные и групповые в одной куче.
Нет строк за месяц — нули, не None и не исключение.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from src.Kate_Fit_Notes.repository import KateFitRepository


def _as_number(value: Any) -> float:
    if value is None:
        return 0
    return value


def _month_start(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    return None


def _normalize_row(row: dict, month: date | None = None) -> dict:
    month_value = month if month is not None else _month_start(row.get("month"))
    return {
        "income": _as_number(row.get("income")),
        "sum_rent": _as_number(row.get("sum_rent")),
        "total_sum": _as_number(row.get("total_sum")),
        "month": month_value,
    }


def _empty_month(year: int, month: int) -> dict:
    return {
        "income": 0,
        "sum_rent": 0,
        "total_sum": 0,
        "month": date(year, month, 1),
    }


class ReportService:
    def __init__(self, repo: KateFitRepository):
        self._repo = repo

    def monthly_report(self) -> list[dict]:
        return [_normalize_row(row) for row in self._repo.get_incom_all_month_balance()]

    def monthly_income(self, year: int, month: int) -> dict:
        target = date(year, month, 1)
        for row in self.monthly_report():
            row_month = row.get("month")
            if row_month is not None and row_month.year == year and row_month.month == month:
                return row
        return _empty_month(year, month)
