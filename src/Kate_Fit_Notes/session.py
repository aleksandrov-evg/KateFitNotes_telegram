"""Состояние сценария бота: один объект на chat_id, без глобальных синглтонов."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def empty_week_dates() -> dict[str, Any]:
    """Ключи кнопок недели, как в show_date: '0'…'6'."""
    return {str(i): None for i in range(7)}


@dataclass
class ScenarioState:
    process: str | None = None
    operation: str | None = None
    client: Any = None
    client_multi: Any = None
    train: Any = None
    date: Any = None
    time: Any = None
    price: Any = None
    list_train: Any = None
    list_client: Any = None
    list_time: Any = None
    is_group: bool | None = None
    train_price: Any = None
    list_multi_select: Any = None
    id_prepaid_row: Any = None
    id_prepaid_data: Any = None
    set_is_complete_true: bool = False
    summ: int | None = None
    count_train: int | None = None
    allow_add_client: bool = False
    week_dates: dict[str, Any] = field(default_factory=empty_week_dates)


class SessionStore:
    """In-memory сессии по chat_id. Не multi-user продукт — только ключ состояния."""

    def __init__(self) -> None:
        self._sessions: dict[int, ScenarioState] = {}

    def get(self, chat_id: int) -> ScenarioState:
        if chat_id not in self._sessions:
            self._sessions[chat_id] = ScenarioState()
        return self._sessions[chat_id]

    def clear(self, chat_id: int, process: str | None = None) -> ScenarioState:
        state = ScenarioState(process=process)
        self._sessions[chat_id] = state
        return state
