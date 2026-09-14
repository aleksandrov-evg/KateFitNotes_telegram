"""Клавиатуры и тексты бота. Без SQL и без send_message."""

from __future__ import annotations

from datetime import date, time
from typing import Any

from telebot import types

from src.Kate_Fit_Notes.domain import price_per_train, time_choice_caption

BACK_TO_MENU = "🔙 В главное меню"
MENU_NEW_CLIENT = "➕ Новый клиент"
MENU_ADD_PAYMENT = "Добавить оплату"
MENU_REPORT = "💰 Отчет по тренировкам"
MENU_PERSONAL = "➕🤸‍ Добавить перс. тренировку"
MENU_GROUP = "➕👯 Добавить груп. тренировку"
GREETING = "Привет, Катюнь! Что будем делать?"
ACCESS_DENIED = "Нет доступа"


def main_menu_markup() -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        MENU_NEW_CLIENT,
        MENU_ADD_PAYMENT,
        MENU_REPORT,
        MENU_PERSONAL,
        MENU_GROUP,
    )
    markup.add(BACK_TO_MENU)
    return markup


def back_to_menu_markup() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(BACK_TO_MENU)


def confirm_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Добавить", callback_data="approve_add"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_add"),
    )
    return markup


def train_types_markup(trains: list[dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        *[
            types.InlineKeyboardButton(train["type_train"], callback_data=str(train["id"]))
            for train in trains
        ]
    )
    return markup


def client_list_markup(clients: list[dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    if clients:
        markup.add(
            *[
                types.InlineKeyboardButton(client["name"], callback_data=str(client["client"]))
                for client in clients
            ]
        )
    markup.add(
        types.InlineKeyboardButton("Показать всех клиентов", callback_data="show_all_client_single")
    )
    return markup


def multi_client_markup(clients: list[dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for client in clients:
        mark = "✅" if client.get("select") else ""
        buttons.append(
            types.InlineKeyboardButton(
                f"{mark}{client['name']}{mark}",
                callback_data=str(client["client"]),
            )
        )
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("Показать всех клиентов", callback_data="show_all_client_multi"))
    markup.add(types.InlineKeyboardButton("Подвердить ввод", callback_data="confirm_multi_list_client"))
    return markup


def week_markup(days: list[date]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=5)
    markup.add(
        types.InlineKeyboardButton("<< неделя", callback_data="prev_week"),
        types.InlineKeyboardButton("Эта неделя", callback_data="current_week"),
        types.InlineKeyboardButton("неделя >>", callback_data="next_week"),
    )
    markup.add(
        *[
            types.InlineKeyboardButton(f"{day:%d %a}", callback_data=day.isoformat())
            for day in days
        ]
    )
    return markup


def slots_markup(slots: list[time]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        *[
            types.InlineKeyboardButton(f"{slot:%H:%M}", callback_data=slot.strftime("%H:%M"))
            for slot in slots
        ]
    )
    return markup


def schedule_menu_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Вывести расписание на сегодня", callback_data="show_schedule_today"),
        types.InlineKeyboardButton("Вывести расписание на дату", callback_data="show_schedule_date"),
        types.InlineKeyboardButton("Вывести расписание клиента", callback_data="show_schedule_client"),
    )
    return markup


def report_text(rows: list[dict] | None) -> str:
    if not rows:
        return (
            "Дата:     *—*\n"
            "Прибыль:  *0*\n"
            "Аренда:   *0*\n"
            "Всего:    *0*\n"
            "========================="
        )
    return "\n".join(
        [
            f'Дата:     *{row["month"].strftime("%m.%Y")}*\n'
            f'Прибыль:  *{row["income"]}*\n'
            f'Аренда:   *{row["sum_rent"]}*\n'
            f'Всего:    *{row["total_sum"]}*\n'
            f"========================="
            for row in rows
        ]
    )


def price_prompt_text(additional_text: str = "") -> str:
    return f"Укажи сумму тренировки\n{additional_text}"


def time_slots_caption(session_date: Any) -> str:
    return time_choice_caption(session_date)


def booking_confirm_text(
    train_name: str,
    text_client: str,
    session_date: Any,
    session_time: Any,
    price: Any,
    additional_info: str = "",
) -> str:
    return (
        f"Добавить тренировку *{train_name}*\n"
        f"{text_client}"
        f"На дату: *{session_date}*\n"
        f"На время: *{session_time}*\n"
        f"Цена тренировки *{price}*?"
        f"{additional_info}"
    )


def prepaid_confirm_text(client: dict, train: dict, summ: int, count: int) -> str:
    return (
        "Добавление предоплаты\n"
        f"Клиент: {client['name']} {client['surname']}\n"
        f"Тренировка: {train['type_train']}\n"
        f"Общая сумма: {summ}\n"
        f"Количество тренировок: {count}\n"
        f"Стоимость 1 тренировки: {price_per_train(summ, count)}\n"
    )
