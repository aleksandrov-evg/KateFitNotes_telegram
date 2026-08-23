"""Чистые функции валидации и расчётов. Без Telegram и БД."""

from __future__ import annotations

import datetime
from typing import Any, Iterable, Literal

WORK_HOUR_START = 7
WORK_HOUR_END = 23  # исключительно: последний слот 22:00
ACCOUNTING_NOW_SQL = "NOW()"
GROUP_CLIENT_ID = -1

PhoneStatus = Literal["invalid", "ok"]
WeekShift = Literal["prev", "current", "next"]


def normalize_phone(raw: str | None) -> int | None:
    """+7 / 7 / 8 и 11–12 символов → 10 цифр. Иначе None, не 0."""
    if raw is None:
        return None
    phone = str(raw).strip()
    if len(phone) == 12 and phone[:2] == "+7" and phone[2:].isdigit():
        return int(phone[2:])
    if len(phone) == 11 and phone.isdigit() and phone[0] in ("7", "8"):
        return int(phone[1:])
    return None


def new_client_phone_status(raw: str | None) -> PhoneStatus:
    """Невалидный номер — invalid, не duplicate."""
    if normalize_phone(raw) is None:
        return "invalid"
    return "ok"


def parse_price(text: str | None) -> int | None:
    if text is None or not str(text).isdigit():
        return None
    return int(text)


def parse_prepaid(text: str | None) -> tuple[int, int] | None:
    """'<сумма> <количество>'. Лишние пробелы допустимы; 0 тренировок — отказ."""
    if text is None:
        return None
    parts = str(text).split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    summ = int(parts[0])
    count_train = int(parts[1])
    if count_train == 0:
        return None
    return summ, count_train


def price_per_train(summ: int, count_train: int) -> float:
    if count_train == 0:
        raise ValueError("количество тренировок не может быть 0")
    return summ / count_train


def work_slots() -> list[datetime.time]:
    return [datetime.time(hour, 0) for hour in range(WORK_HOUR_START, WORK_HOUR_END)]


def available_slots(occupied: Iterable[datetime.time] | None = None) -> list[datetime.time]:
    """Рабочие слоты минус занятые. Часы вне 07–23 не добавляются."""
    busy = set(occupied or ())
    return sorted(set(work_slots()) - busy)


def week_days(anchor: datetime.date) -> list[datetime.date]:
    monday = anchor - datetime.timedelta(days=anchor.isoweekday() - 1)
    return [monday + datetime.timedelta(days=offset) for offset in range(7)]


def shift_week(
    anchor: datetime.date,
    direction: WeekShift,
    today: datetime.date | None = None,
) -> datetime.date:
    if direction == "current":
        return today if today is not None else datetime.date.today()
    monday = week_days(anchor)[0]
    if direction == "prev":
        return monday - datetime.timedelta(days=7)
    if direction == "next":
        return monday + datetime.timedelta(days=7)
    raise ValueError(f"неизвестное направление недели: {direction}")


def should_complete_prepaid(count_train: int, used_count: int) -> bool:
    return count_train - used_count == 1


def time_choice_caption(date: datetime.date | str) -> str:
    return f"Выбор времени на дату: {date}"


def format_client_list(ids: Iterable | None) -> str:
    """Текущий формат записи: строка PostgreSQL-массива {id1,id2,...}."""
    if not ids:
        return "{}"
    return "{" + ",".join(str(item) for item in ids) + "}"


def parse_client_list(raw: Any) -> list[int]:
    """Строка {1,2,3} или bigint[] из драйвера → список id."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [int(item) for item in raw]
    text = str(raw).strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    if not text.strip():
        return []
    return [int(part.strip()) for part in text.split(",") if part.strip()]
