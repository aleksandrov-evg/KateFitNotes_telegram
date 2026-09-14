"""Юнит-тесты SessionStore / ScenarioState. Без Telegram и БД."""

from datetime import date

from src.Kate_Fit_Notes.session import ScenarioState, SessionStore, empty_week_dates

CHAT_A = 1001
CHAT_B = 2002


def test_get_creates_empty_state():
    store = SessionStore()
    state = store.get(CHAT_A)
    assert isinstance(state, ScenarioState)
    assert state.process is None
    assert state.operation is None
    assert state.allow_add_client is False
    assert list(state.week_dates) == [str(i) for i in range(7)]
    assert store.get(CHAT_A) is state


def test_two_chat_ids_are_independent():
    store = SessionStore()
    a = store.get(CHAT_A)
    b = store.get(CHAT_B)
    a.process = "add_single_train_in_schedule"
    a.operation = "choose_client"
    a.client = {"client": 9001112233, "name": "Анна"}
    b.process = "add_money_in_accounting"
    b.operation = "choose_train"
    b.client = {"client": 9004445566, "name": "Борис"}

    assert store.get(CHAT_A).process == "add_single_train_in_schedule"
    assert store.get(CHAT_A).operation == "choose_client"
    assert store.get(CHAT_A).client["name"] == "Анна"
    assert store.get(CHAT_B).process == "add_money_in_accounting"
    assert store.get(CHAT_B).operation == "choose_train"
    assert store.get(CHAT_B).client["name"] == "Борис"
    assert store.get(CHAT_A) is not store.get(CHAT_B)


def test_clear_one_chat_does_not_reset_the_other():
    store = SessionStore()
    a = store.clear(CHAT_A, "add_single_train_in_schedule")
    b = store.clear(CHAT_B, "add_money_in_accounting")
    a.operation = "choose_date"
    b.operation = "total_summ_and_number_train"
    b.summ = 1000
    b.count_train = 10

    cleared = store.clear(CHAT_A)
    assert cleared.process is None
    assert store.get(CHAT_A).operation is None
    assert store.get(CHAT_A) is not a
    assert store.get(CHAT_B) is b
    assert store.get(CHAT_B).process == "add_money_in_accounting"
    assert store.get(CHAT_B).operation == "total_summ_and_number_train"
    assert store.get(CHAT_B).summ == 1000
    assert store.get(CHAT_B).count_train == 10


def test_booking_and_payment_are_not_a_shared_singleton():
    store = SessionStore()
    booking = store.clear(CHAT_A, "add_single_train_in_schedule")
    payment = store.clear(CHAT_B, "add_money_in_accounting")
    booking.operation = "input_train_price"
    booking.train_price = 1500
    payment.operation = "confirm_add_accounting"
    payment.summ = 5000
    payment.count_train = 8

    assert booking is not payment
    assert store.get(CHAT_A).process == "add_single_train_in_schedule"
    assert store.get(CHAT_A).train_price == 1500
    assert store.get(CHAT_B).process == "add_money_in_accounting"
    assert store.get(CHAT_B).summ == 5000
    assert store.get(CHAT_B).count_train == 8


def test_restart_chat_a_does_not_break_unfinished_chat_b():
    store = SessionStore()
    store.clear(CHAT_A, "add_multi_train_in_schedule")
    store.get(CHAT_A).operation = "choose_client_multi"
    store.get(CHAT_A).client_multi = [(1, "Анна Иванова")]
    store.clear(CHAT_B, "add_money_in_accounting")
    store.get(CHAT_B).operation = "choose_client"
    store.get(CHAT_B).client = {"client": 9004445566, "name": "Борис"}

    store.clear(CHAT_A)

    assert store.get(CHAT_A).process is None
    assert store.get(CHAT_A).client_multi is None
    assert store.get(CHAT_B).process == "add_money_in_accounting"
    assert store.get(CHAT_B).operation == "choose_client"
    assert store.get(CHAT_B).client["name"] == "Борис"


def test_allow_add_client_is_isolated_per_chat():
    store = SessionStore()
    store.get(CHAT_A).allow_add_client = True
    assert store.get(CHAT_B).allow_add_client is False
    store.get(CHAT_B).allow_add_client = True
    store.get(CHAT_A).allow_add_client = False
    assert store.get(CHAT_B).allow_add_client is True


def test_week_dates_are_isolated_per_chat():
    store = SessionStore()
    monday = date(2026, 8, 17)
    store.get(CHAT_A).week_dates["0"] = monday
    assert store.get(CHAT_B).week_dates["0"] is None
    assert store.get(CHAT_A).week_dates is not store.get(CHAT_B).week_dates
    assert empty_week_dates() == {str(i): None for i in range(7)}


def test_clear_resets_allow_add_client_and_week_dates():
    store = SessionStore()
    state = store.get(CHAT_A)
    state.allow_add_client = True
    state.week_dates["0"] = date(2026, 8, 17)
    store.clear(CHAT_A, "add_single_train_in_schedule")
    fresh = store.get(CHAT_A)
    assert fresh.process == "add_single_train_in_schedule"
    assert fresh.allow_add_client is False
    assert fresh.week_dates["0"] is None
