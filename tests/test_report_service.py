"""Автотесты ReportService: формула прибыли, нули, границы месяца.

Не импортирует bot.py и sql.py.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from src.Kate_Fit_Notes.domain import GROUP_CLIENT_ID
from src.Kate_Fit_Notes.repository import PostgresRepository
from src.Kate_Fit_Notes.services.report import ReportService

PERSONAL_TRAIN_ID = 1
GROUP_TRAIN_ID = 2


class FakeReportRepo:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def get_incom_all_month_balance(self):
        return list(self.rows)


@pytest.fixture
def repo(migrated_database, db_conn):
    repository = PostgresRepository.from_dsn(migrated_database)
    try:
        yield repository
    finally:
        repository.close()


@pytest.fixture
def service(repo):
    return ReportService(repo)


class TestMonthlyIncomeUnit:
    def test_empty_repo_returns_zeros(self):
        result = ReportService(FakeReportRepo()).monthly_income(2026, 8)
        assert result["income"] == 0
        assert result["sum_rent"] == 0
        assert result["total_sum"] == 0
        assert result["month"] == date(2026, 8, 1)

    def test_null_sums_become_zero(self):
        fake = FakeReportRepo(
            [
                {
                    "income": None,
                    "sum_rent": None,
                    "total_sum": None,
                    "month": datetime(2026, 8, 1),
                }
            ]
        )
        result = ReportService(fake).monthly_income(2026, 8)
        assert result["income"] == 0
        assert result["sum_rent"] == 0
        assert result["total_sum"] == 0

    def test_filters_requested_month(self):
        fake = FakeReportRepo(
            [
                {
                    "income": 100,
                    "sum_rent": 10,
                    "total_sum": 110,
                    "month": datetime(2026, 7, 1),
                },
                {
                    "income": 500,
                    "sum_rent": 50,
                    "total_sum": 550,
                    "month": datetime(2026, 8, 1),
                },
            ]
        )
        result = ReportService(fake).monthly_income(2026, 8)
        assert result["income"] == 500
        assert result["sum_rent"] == 50
        assert result["total_sum"] == 550


class TestMonthlyIncomeIntegration:
    def test_personal_and_group_formula(
        self, service, make_client, make_schedule
    ):
        client = make_client(phone=9201112401)
        make_schedule(
            client=client["phone"],
            session_date=date(2026, 8, 10),
            session_time=time(10, 0),
            type_train_id=PERSONAL_TRAIN_ID,
            price=1000,
            rent_debt=200,
            is_group=False,
        )
        make_schedule(
            client=GROUP_CLIENT_ID,
            session_date=date(2026, 8, 10),
            session_time=time(11, 0),
            type_train_id=GROUP_TRAIN_ID,
            price=3000,
            rent_debt=500,
            is_group=True,
            client_list=[client["phone"]],
        )
        result = service.monthly_income(2026, 8)
        assert result["total_sum"] == 4000
        assert result["sum_rent"] == 700
        assert result["income"] == 3300
        assert result["month"] == date(2026, 8, 1)

    def test_empty_month_zeros(self, service):
        result = service.monthly_income(2026, 1)
        assert result["income"] == 0
        assert result["sum_rent"] == 0
        assert result["total_sum"] == 0
        assert result["month"] == date(2026, 1, 1)

    def test_rent_debt_reduces_income(
        self, service, make_client, make_schedule
    ):
        client = make_client(phone=9201112402)
        make_schedule(
            client=client["phone"],
            session_date=date(2026, 8, 12),
            session_time=time(10, 0),
            type_train_id=PERSONAL_TRAIN_ID,
            price=2000,
            rent_debt=1500,
        )
        result = service.monthly_income(2026, 8)
        assert result["total_sum"] == 2000
        assert result["sum_rent"] == 1500
        assert result["income"] == 500

    def test_month_boundaries(self, service, make_client, make_schedule):
        client = make_client(phone=9201112403)
        make_schedule(
            client=client["phone"],
            session_date=date(2026, 8, 1),
            session_time=time(10, 0),
            price=100,
            rent_debt=10,
        )
        make_schedule(
            client=client["phone"],
            session_date=date(2026, 8, 31),
            session_time=time(11, 0),
            price=200,
            rent_debt=20,
        )
        make_schedule(
            client=client["phone"],
            session_date=date(2026, 7, 31),
            session_time=time(10, 0),
            price=9999,
            rent_debt=1,
        )
        make_schedule(
            client=client["phone"],
            session_date=date(2026, 9, 1),
            session_time=time(10, 0),
            price=8888,
            rent_debt=2,
        )
        august = service.monthly_income(2026, 8)
        assert august["total_sum"] == 300
        assert august["sum_rent"] == 30
        assert august["income"] == 270
        july = service.monthly_income(2026, 7)
        assert july["total_sum"] == 9999
        september = service.monthly_income(2026, 9)
        assert september["total_sum"] == 8888
