"""Юнит-тесты чистых функций этапа 1. Без Telegram и БД."""

from datetime import date, time
from pathlib import Path

import pytest

from src.Kate_Fit_Notes.domain import (
    ACCOUNTING_NOW_SQL,
    GROUP_CLIENT_ID,
    available_slots,
    format_client_list,
    new_client_phone_status,
    normalize_phone,
    parse_client_list,
    parse_prepaid,
    parse_price,
    price_per_train,
    shift_week,
    should_complete_prepaid,
    time_choice_caption,
    week_days,
    work_slots,
)


class TestNormalizePhone:
    def test_plus7(self):
        assert normalize_phone("+79001234567") == 9001234567

    def test_leading_7(self):
        assert normalize_phone("79001234567") == 9001234567

    def test_leading_8(self):
        assert normalize_phone("89001234567") == 9001234567

    def test_garbage(self):
        assert normalize_phone("мусор") is None

    def test_short_number(self):
        assert normalize_phone("900123") is None

    def test_zero_is_invalid_not_zero_int(self):
        assert normalize_phone("0") is None
        assert normalize_phone("0") != 0


class TestNewClientPhoneStatus:
    def test_invalid_is_not_duplicate(self):
        assert new_client_phone_status("мусор") == "invalid"
        assert new_client_phone_status("0") == "invalid"
        assert new_client_phone_status("123") == "invalid"

    def test_valid_is_ok(self):
        assert new_client_phone_status("+79001234567") == "ok"
        assert new_client_phone_status("89001234567") == "ok"


class TestParsePrice:
    def test_digits_only(self):
        assert parse_price("1000") == 1000

    def test_empty(self):
        assert parse_price("") is None

    def test_non_number(self):
        assert parse_price("abc") is None
        assert parse_price("12.5") is None


class TestParsePrepaid:
    def test_sum_and_count(self):
        assert parse_prepaid("1000 10") == (1000, 10)

    def test_extra_spaces(self):
        assert parse_prepaid("  1000   10  ") == (1000, 10)

    def test_zero_trainings(self):
        assert parse_prepaid("1000 0") is None

    def test_one_part(self):
        assert parse_prepaid("1000") is None


class TestPricePerTrain:
    def test_division(self):
        assert price_per_train(1000, 10) == 100

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            price_per_train(1000, 0)


class TestSlots:
    def test_full_workday_07_to_22(self):
        slots = work_slots()
        assert len(slots) == 16
        assert slots[0] == time(7, 0)
        assert slots[-1] == time(22, 0)
        assert time(6, 0) not in slots
        assert time(23, 0) not in slots

    def test_occupied_hour_disappears(self):
        result = available_slots([time(10, 0)])
        assert time(10, 0) not in result
        assert time(9, 0) in result
        assert time(11, 0) in result

    def test_boundaries_6_and_23_never_appear(self):
        result = available_slots([time(6, 0), time(23, 0)])
        assert time(6, 0) not in result
        assert time(23, 0) not in result
        assert time(7, 0) in result
        assert time(22, 0) in result


class TestWeek:
    ANCHOR = date(2026, 8, 19)  # среда

    def test_week_days_monday_to_sunday(self):
        days = week_days(self.ANCHOR)
        assert days[0] == date(2026, 8, 17)
        assert days[-1] == date(2026, 8, 23)
        assert len(days) == 7

    def test_prev_week(self):
        assert shift_week(self.ANCHOR, "prev") == date(2026, 8, 10)

    def test_next_week(self):
        assert shift_week(self.ANCHOR, "next") == date(2026, 8, 24)

    def test_current_week_uses_today(self):
        today = date(2026, 1, 15)
        assert shift_week(self.ANCHOR, "current", today=today) == today


class TestShouldCompletePrepaid:
    def test_last_session_true(self):
        assert should_complete_prepaid(count_train=10, used_count=9) is True

    def test_not_last_false(self):
        assert should_complete_prepaid(count_train=10, used_count=8) is False
        assert should_complete_prepaid(count_train=10, used_count=10) is False


class TestTimeChoiceCaption:
    def test_contains_date_not_operation(self):
        caption = time_choice_caption(date(2026, 8, 19))
        assert "2026-08-19" in caption
        assert "choose_time" not in caption
        assert caption.startswith("Выбор времени на дату:")


class TestAccountingNowSql:
    def test_now_is_sql_function_not_quoted_string(self):
        assert ACCOUNTING_NOW_SQL == "NOW()"
        assert "'" not in ACCOUNTING_NOW_SQL
        assert '"' not in ACCOUNTING_NOW_SQL

    def test_repository_inserts_unquoted_now(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "Kate_Fit_Notes"
            / "repository.py"
        ).read_text(encoding="utf-8")
        assert "'now()'" not in source
        assert "ACCOUNTING_NOW_SQL" in source


class TestClientListFormat:
    def test_format_ids_as_braces(self):
        assert format_client_list([9001112233, 9001112234]) == "{9001112233,9001112234}"
        assert format_client_list([]) == "{}"
        assert format_client_list(None) == "{}"

    def test_parse_braces_string(self):
        assert parse_client_list("{9001112233,9001112234}") == [9001112233, 9001112234]
        assert parse_client_list("{}") == []
        assert parse_client_list(None) == []

    def test_parse_postgres_array(self):
        assert parse_client_list([9001112233, 9001112234]) == [9001112233, 9001112234]
        assert parse_client_list((9001112233,)) == [9001112233]

    def test_group_client_id_is_minus_one(self):
        assert GROUP_CLIENT_ID == -1
