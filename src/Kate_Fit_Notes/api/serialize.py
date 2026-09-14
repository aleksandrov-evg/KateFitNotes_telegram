"""Словари сервисов/репозитория → ответы API."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from src.Kate_Fit_Notes.api.schemas import (
    BookingOut,
    ClientOut,
    MonthReportOut,
    PrepaidOut,
    TrainTypeOut,
)


def client_out(row: dict) -> ClientOut:
    client_id = row.get("id")
    if client_id is None:
        client_id = row.get("client")
    return ClientOut(
        id=int(client_id),
        phone=int(row["phone"]),
        name=str(row.get("name") or ""),
        surname=str(row.get("surname") or ""),
    )


def train_type_out(row: dict) -> TrainTypeOut:
    rent = row.get("rent_debt")
    return TrainTypeOut(
        id=int(row["id"]),
        type_train=str(row.get("type_train") or ""),
        group_train=bool(row.get("group_train")),
        rent_debt=None if rent is None else float(rent),
    )


def slot_label(value: Any) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    text = str(value)
    return text[:5] if len(text) >= 5 else text


def booking_out(row: dict) -> BookingOut:
    session_date = row["date"]
    session_time = row["time"]
    if isinstance(session_time, datetime):
        session_time = session_time.time()
    accounting_id = row.get("accounting_id")
    return BookingOut(
        client=row.get("client"),
        participants=row.get("participants"),
        date=session_date,
        time=session_time,
        price=None if row.get("price") is None else float(row["price"]),
        type_train_id=int(row["type_train_id"]),
        accounting_id=None if accounting_id is None else int(accounting_id),
    )


def prepaid_out(row: dict) -> PrepaidOut:
    return PrepaidOut(
        client_id=int(row["client_id"]),
        type_train_id=int(row["type_train_id"]),
        summ=int(row["summ"]),
        count_train=int(row["count_train"]),
        price_per_train=float(row["price_per_train"]),
    )


def month_report_out(row: dict) -> MonthReportOut:
    month = row.get("month")
    if isinstance(month, datetime):
        month = month.date()
    elif month is not None and not isinstance(month, date):
        month = None
    return MonthReportOut(
        income=float(row.get("income") or 0),
        sum_rent=float(row.get("sum_rent") or 0),
        total_sum=float(row.get("total_sum") or 0),
        month=month,
    )
