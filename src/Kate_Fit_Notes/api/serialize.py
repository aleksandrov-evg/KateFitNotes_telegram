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
    add_time = row.get("add_time")
    if isinstance(add_time, datetime):
        add_time = add_time.date()
    inactive = row.get("inactive")
    return ClientOut(
        id=int(client_id),
        phone=int(row["phone"]),
        name=str(row.get("name") or ""),
        surname=str(row.get("surname") or ""),
        inactive=None if inactive is None else bool(inactive),
        add_time=add_time if isinstance(add_time, date) else None,
    )


def train_type_out(row: dict) -> TrainTypeOut:
    rent = row.get("rent_debt")
    location = row.get("location")
    return TrainTypeOut(
        id=int(row["id"]),
        type_train=str(row.get("type_train") or ""),
        group_train=bool(row.get("group_train")),
        rent_debt=None if rent is None else float(rent),
        location=None if location is None else str(location),
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
    schedule_id = row.get("id")
    client_id = row.get("client")
    if client_id is None:
        client_id = row.get("client_id")
    rent = row.get("rent_debt")
    add_time = row.get("add_time")
    is_group = row.get("is_group")
    participants = row.get("participants")
    if participants is None and client_id is not None and not is_group:
        participants = [int(client_id)]
    return BookingOut(
        id=None if schedule_id is None else int(schedule_id),
        client=None if client_id is None else int(client_id),
        participants=None if participants is None else [int(item) for item in participants],
        date=session_date,
        time=session_time,
        price=None if row.get("price") is None else float(row["price"]),
        rent_debt=None if rent is None else float(rent),
        type_train_id=int(row["type_train_id"]),
        accounting_id=None if accounting_id is None else int(accounting_id),
        is_group=None if is_group is None else bool(is_group),
        add_time=add_time if isinstance(add_time, datetime) else None,
    )


def prepaid_out(row: dict) -> PrepaidOut:
    package_id = row.get("id")
    used = row.get("used_count")
    count_train = int(row["count_train"])
    remaining = row.get("remaining")
    if remaining is None and used is not None:
        remaining = count_train - int(used)
    is_complete = row.get("is_complete")
    return PrepaidOut(
        id=None if package_id is None else int(package_id),
        client_id=int(row["client_id"]),
        type_train_id=int(row["type_train_id"]),
        summ=int(row["summ"]),
        count_train=count_train,
        price_per_train=float(row["price_per_train"]),
        is_complete=None if is_complete is None else bool(is_complete),
        used_count=None if used is None else int(used),
        remaining=None if remaining is None else int(remaining),
        created_at=row.get("created_at") if isinstance(row.get("created_at"), datetime) else None,
        updated_at=row.get("updated_at") if isinstance(row.get("updated_at"), datetime) else None,
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
