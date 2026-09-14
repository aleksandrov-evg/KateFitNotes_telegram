"""Автотесты Telegram-адаптера. Без прод-БД и живого токена."""

from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace
from unittest.mock import MagicMock

import telebot

import bot as bot_module
from bot import create_bot
from src.Kate_Fit_Notes.bot_ui import (
    ACCESS_DENIED,
    BACK_TO_MENU,
    GREETING,
    MENU_ADD_PAYMENT,
    MENU_PERSONAL,
    MENU_REPORT,
    client_list_markup,
    slots_markup,
    train_types_markup,
    week_markup,
)
from src.Kate_Fit_Notes.session import SessionStore
from src.Kate_Fit_Notes.settings import Settings

CHAT_A = 1001
CHAT_B = 2002
CHAT_STRANGER = 9999
CLIENT = {"client": 42, "name": "Анна", "surname": "Иванова"}
TRAIN = {"id": 1, "type_train": "силовая 1 чел", "group_train": False}
SESSION_DATE = date(2026, 8, 24)
SESSION_TIME = time(10, 0)

SETTINGS = Settings(
    telegram_token="test-token",
    sql_user="user",
    sql_password="pass",
    sql_database="Kate_fitness_test",
    sql_host="localhost",
    sql_port=5433,
)


class FakeBotRepo:
    def __init__(self):
        self.select_last_client_calls = []
        self.list_all_train_calls = []
        self.income_calls = 0
        self.clients = [dict(CLIENT)]
        self.trains = [dict(TRAIN)]

    def select_last_client(self, number_client=0):
        self.select_last_client_calls.append(number_client)
        return list(self.clients)

    def show_all_clients(self):
        return list(self.clients)

    def list_all_train(self, group):
        self.list_all_train_calls.append(group)
        return [dict(row) for row in self.trains if bool(row.get("group_train")) is bool(group)]

    def get_incom_all_month_balance(self):
        self.income_calls += 1
        return []

    def search_client(self, phone_number):
        return []

    def insert_client_data(self, *args, **kwargs):
        return 1

    def select_time_at_data(self, session_date):
        return []

    def get_train(self, train_id):
        return next((dict(row) for row in self.trains if row["id"] == train_id), None)

    def get_active_prepaid_for_client(self, client_id, type_train_id):
        return []

    def get_count_prepaid_train(self, client_id, type_train_id):
        return []

    def get_last_price_for_train(self, client_id, type_train_id):
        return []


def make_message(chat_id, text=None, content_type="text"):
    chat = SimpleNamespace(id=chat_id)
    return SimpleNamespace(
        chat=chat,
        from_user=SimpleNamespace(id=chat_id),
        text=text,
        content_type=content_type,
        contact=None,
        id=1,
    )


def make_call(chat_id, data):
    message = make_message(chat_id)
    message.id = 10
    return SimpleNamespace(message=message, data=data)


def make_app(repo=None, sessions=None, allowed_chat_ids=None):
    app = create_bot(
        SETTINGS,
        repo or FakeBotRepo(),
        sessions or SessionStore(),
        allowed_chat_ids=(
            frozenset({CHAT_A, CHAT_B})
            if allowed_chat_ids is None
            else frozenset(allowed_chat_ids)
        ),
    )
    app.bot.send_message = MagicMock()
    app.bot.delete_message = MagicMock()
    return app


def test_import_bot_does_not_require_token_or_start_polling(monkeypatch):
    monkeypatch.delenv("TG_TOKEN", raising=False)
    monkeypatch.setattr(
        telebot.TeleBot,
        "infinity_polling",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("polling")),
    )
    assert callable(bot_module.create_bot)
    assert getattr(bot_module, "bot", None) is None


def test_personal_train_button_lists_recent_clients():
    repo = FakeBotRepo()
    app = make_app(repo)
    app.get_text_messages(make_message(CHAT_A, MENU_PERSONAL))
    assert app.sessions.get(CHAT_A).process == "add_single_train_in_schedule"
    assert repo.select_last_client_calls == [0]
    assert app.sessions.get(CHAT_A).list_client[0]["client"] == CLIENT["client"]


def test_add_payment_button_starts_prepaid_process():
    repo = FakeBotRepo()
    app = make_app(repo)
    app.get_text_messages(make_message(CHAT_A, MENU_ADD_PAYMENT))
    assert app.sessions.get(CHAT_A).process == "add_money_in_accounting"
    assert repo.select_last_client_calls == [0]


def test_report_button_calls_monthly_report():
    repo = FakeBotRepo()
    app = make_app(repo)
    app.report_service.monthly_report = MagicMock(return_value=[])
    app.get_text_messages(make_message(CHAT_A, MENU_REPORT))
    app.report_service.monthly_report.assert_called_once_with()


def test_approve_add_calls_book_personal_with_state_ids():
    app = make_app()
    app.booking_service.book_personal = MagicMock()
    state = app.sessions.clear(CHAT_A, "add_single_train_in_schedule")
    state.operation = "confirm_add"
    state.is_group = False
    state.client = dict(CLIENT)
    state.train = dict(TRAIN)
    state.date = SESSION_DATE
    state.time = SESSION_TIME
    state.train_price = 1500
    app.callback_inline(make_call(CHAT_A, "approve_add"))
    app.booking_service.book_personal.assert_called_once_with(
        client_id=42,
        type_train_id=1,
        session_date=SESSION_DATE,
        session_time=SESSION_TIME,
        price=1500,
    )


def test_client_callback_uses_id_not_index():
    app = make_app()
    state = app.sessions.clear(CHAT_A, "add_single_train_in_schedule")
    state.operation = "choose_client"
    state.list_client = [
        {"client": 42, "name": "Анна", "surname": "Иванова"},
        {"client": 43, "name": "Борис", "surname": "Петров"},
    ]
    app.booking_service.list_train_types = MagicMock(return_value=[dict(TRAIN)])
    app.callback_inline(make_call(CHAT_A, "43"))
    assert app.sessions.get(CHAT_A).client["client"] == 43
    app.booking_service.list_train_types.assert_called_once_with(False)


def test_stale_client_callback_does_not_crash():
    app = make_app()
    state = app.sessions.clear(CHAT_A, "add_single_train_in_schedule")
    state.operation = "choose_client"
    state.list_client = [dict(CLIENT)]
    app.callback_inline(make_call(CHAT_A, "0"))
    assert app.sessions.get(CHAT_A).client is None


def test_main_menu_clears_only_current_chat():
    sessions = SessionStore()
    sessions.clear(CHAT_B, "add_money_in_accounting")
    sessions.get(CHAT_B).operation = "choose_client"
    sessions.get(CHAT_B).client = dict(CLIENT)
    app = make_app(sessions=sessions)
    app.sessions.clear(CHAT_A, "add_single_train_in_schedule")
    app.get_text_messages(make_message(CHAT_A, BACK_TO_MENU))
    assert app.sessions.get(CHAT_A).process is None
    assert app.sessions.get(CHAT_B).process == "add_money_in_accounting"
    assert app.sessions.get(CHAT_B).client["name"] == "Анна"


def test_markup_callback_data_is_entity_id_not_index():
    client_markup = client_list_markup([CLIENT])
    assert client_markup.keyboard[0][0].callback_data == "42"
    train_markup = train_types_markup([TRAIN])
    assert train_markup.keyboard[0][0].callback_data == "1"
    day = date(2026, 8, 24)
    date_markup = week_markup([day])
    day_buttons = [btn for row in date_markup.keyboard for btn in row if btn.callback_data == "2026-08-24"]
    assert day_buttons
    slot_markup = slots_markup([SESSION_TIME])
    assert slot_markup.keyboard[0][0].callback_data == "10:00"


def test_stranger_start_does_not_clear_or_greet():
    sessions = SessionStore()
    sessions.clear(CHAT_A, "add_single_train_in_schedule")
    app = make_app(sessions=sessions)
    app.start(make_message(CHAT_STRANGER, "/start"))
    texts = [call.args[1] for call in app.bot.send_message.call_args_list]
    assert ACCESS_DENIED in texts
    assert GREETING not in texts
    assert app.sessions.get(CHAT_A).process == "add_single_train_in_schedule"


def test_stranger_menu_does_not_call_services():
    repo = FakeBotRepo()
    app = make_app(repo)
    app.client_service.create = MagicMock()
    app.booking_service.book_personal = MagicMock()
    app.report_service.monthly_report = MagicMock()
    app.get_text_messages(make_message(CHAT_STRANGER, MENU_PERSONAL))
    app.get_text_messages(make_message(CHAT_STRANGER, MENU_REPORT))
    assert repo.select_last_client_calls == []
    assert repo.income_calls == 0
    app.client_service.create.assert_not_called()
    app.booking_service.book_personal.assert_not_called()
    app.report_service.monthly_report.assert_not_called()
    texts = [call.args[1] for call in app.bot.send_message.call_args_list]
    assert texts == [ACCESS_DENIED, ACCESS_DENIED]


def test_stranger_callback_does_not_book():
    app = make_app()
    app.booking_service.book_personal = MagicMock()
    state = app.sessions.clear(CHAT_STRANGER, "add_single_train_in_schedule")
    state.operation = "confirm_add"
    state.is_group = False
    state.client = dict(CLIENT)
    state.train = dict(TRAIN)
    state.date = SESSION_DATE
    state.time = SESSION_TIME
    state.train_price = 1500
    app.callback_inline(make_call(CHAT_STRANGER, "approve_add"))
    app.booking_service.book_personal.assert_not_called()
