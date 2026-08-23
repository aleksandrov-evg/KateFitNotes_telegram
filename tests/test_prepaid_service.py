"""Автотесты PrepaidService: пакет, списание, эвристика JOIN.

Не импортирует bot.py и sql.py.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from src.Kate_Fit_Notes.domain import parse_prepaid
from src.Kate_Fit_Notes.repository import PostgresRepository
from src.Kate_Fit_Notes.services.booking import BookingService
from src.Kate_Fit_Notes.services.errors import InvalidPrepaidError, MultiplePrepaidError
from src.Kate_Fit_Notes.services.prepaid import PrepaidService

PERSONAL_TRAIN_ID = 1
OTHER_PERSONAL_TRAIN_ID = 5
SESSION_DATE = date(2026, 8, 24)


class FakePrepaidRepo:
    def __init__(self):
        self.active: list[dict] = []
        self.usage: list[dict] = []
        self.insert_calls: list[tuple] = []

    def get_active_prepaid_for_client(self, client_id, type_train_id):
        return list(self.active)

    def get_count_prepaid_train(self, client_id, type_train_id):
        return list(self.usage)

    def insert_in_accounting(
        self, client_id, summ, count_train, price_per_train, type_train_id
    ):
        self.insert_calls.append(
            (client_id, summ, count_train, price_per_train, type_train_id)
        )
        self.active.append(
            {
                "id": len(self.active) + 1,
                "client_id": client_id,
                "summ": summ,
                "count_train": count_train,
                "price_per_train": price_per_train,
                "type_train_id": type_train_id,
            }
        )


@pytest.fixture
def repo(migrated_database, db_conn):
    repository = PostgresRepository.from_dsn(migrated_database)
    try:
        yield repository
    finally:
        repository.close()


@pytest.fixture
def prepaid(repo):
    return PrepaidService(repo)


@pytest.fixture
def booking(repo):
    return BookingService(repo)


class TestAddPackageUnit:
    def test_parse_1000_10_creates_package(self):
        fake = FakePrepaidRepo()
        parsed = parse_prepaid("1000 10")
        assert parsed == (1000, 10)
        result = PrepaidService(fake).add_package(9001112233, PERSONAL_TRAIN_ID, *parsed)
        assert result["count_train"] == 10
        assert result["price_per_train"] == 100
        assert fake.insert_calls[0][3] == 100

    def test_zero_count_no_insert(self):
        fake = FakePrepaidRepo()
        with pytest.raises(InvalidPrepaidError):
            PrepaidService(fake).add_package(9001112233, PERSONAL_TRAIN_ID, 1000, 0)
        assert fake.insert_calls == []
        assert fake.active == []

    def test_second_package_refused(self):
        fake = FakePrepaidRepo()
        service = PrepaidService(fake)
        service.add_package(9001112233, PERSONAL_TRAIN_ID, 1000, 10)
        with pytest.raises(MultiplePrepaidError):
            service.add_package(9001112233, PERSONAL_TRAIN_ID, 2000, 8)
        assert len(fake.insert_calls) == 1


class TestDebitUnit:
    def test_complete_id_on_last_session(self):
        fake = FakePrepaidRepo()
        fake.active = [{"id": 11, "price_per_train": 1500, "count_train": 10}]
        fake.usage = [{"count_train": 10, "count": 9}]
        assert PrepaidService(fake).complete_id_for_session(9001112233, PERSONAL_TRAIN_ID) == 11

    def test_not_complete_before_last(self):
        fake = FakePrepaidRepo()
        fake.active = [{"id": 11, "price_per_train": 1500, "count_train": 10}]
        fake.usage = [{"count_train": 10, "count": 8}]
        assert PrepaidService(fake).complete_id_for_session(9001112233, PERSONAL_TRAIN_ID) is False

    def test_two_open_packages_raise(self):
        fake = FakePrepaidRepo()
        fake.active = [
            {"id": 11, "price_per_train": 1500, "count_train": 10},
            {"id": 12, "price_per_train": 1600, "count_train": 8},
        ]
        with pytest.raises(MultiplePrepaidError):
            PrepaidService(fake).price_for_session(9001112233, PERSONAL_TRAIN_ID)


class TestAddPackageIntegration:
    def test_package_from_parsed_input(self, prepaid, make_client, db_conn):
        client = make_client(phone=9201112301)
        summ, count = parse_prepaid("1000 10")
        result = prepaid.add_package(client["phone"], PERSONAL_TRAIN_ID, summ, count)
        assert result["count_train"] == 10
        assert result["price_per_train"] == 100
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT count_train, price_per_train, is_complete "
                "FROM main.accounting WHERE client_id = %s",
                (client["phone"],),
            )
            row = cur.fetchone()
        assert row[0] == 10
        assert row[1] == 100
        assert row[2] is False

    def test_zero_count_no_row(self, prepaid, make_client, db_conn):
        client = make_client(phone=9201112302)
        with pytest.raises(InvalidPrepaidError):
            prepaid.add_package(client["phone"], PERSONAL_TRAIN_ID, 1000, 0)
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM main.accounting WHERE client_id = %s",
                (client["phone"],),
            )
            assert cur.fetchone()[0] == 0

    def test_second_open_package_refused(self, prepaid, make_client, db_conn):
        client = make_client(phone=9201112303)
        prepaid.add_package(client["phone"], PERSONAL_TRAIN_ID, 1000, 10)
        with pytest.raises(MultiplePrepaidError):
            prepaid.add_package(client["phone"], PERSONAL_TRAIN_ID, 2000, 8)
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM main.accounting WHERE client_id = %s",
                (client["phone"],),
            )
            assert cur.fetchone()[0] == 1


class TestDebitIntegration:
    def test_n_sessions_then_package_closed(
        self, prepaid, booking, make_client, db_conn
    ):
        client = make_client(phone=9201112304)
        prepaid.add_package(client["phone"], PERSONAL_TRAIN_ID, 2000, 2)
        # эвристика: created_at <= add_time; NOW() пакета не должен быть позже слота
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE main.accounting SET created_at = %s WHERE client_id = %s",
                (datetime(2020, 1, 1), client["phone"]),
            )
        db_conn.commit()
        booking.book_personal(
            client["phone"], PERSONAL_TRAIN_ID, SESSION_DATE, time(10, 0), price=None
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT is_complete FROM main.accounting WHERE client_id = %s",
                (client["phone"],),
            )
            assert cur.fetchone()[0] is False
        booking.book_personal(
            client["phone"], PERSONAL_TRAIN_ID, SESSION_DATE, time(11, 0), price=None
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT is_complete FROM main.accounting WHERE client_id = %s",
                (client["phone"],),
            )
            assert cur.fetchone()[0] is True
        booking.book_personal(
            client["phone"], PERSONAL_TRAIN_ID, SESSION_DATE, time(12, 0), price=None
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT price FROM main.schedule WHERE client = %s AND time = %s",
                (client["phone"], time(12, 0)),
            )
            assert cur.fetchone()[0] is None

    def test_other_type_does_not_increase_used(
        self, prepaid, make_client, make_schedule, db_conn
    ):
        client = make_client(phone=9201112305)
        prepaid.add_package(client["phone"], PERSONAL_TRAIN_ID, 1000, 10)
        make_schedule(
            client=client["phone"],
            session_date=SESSION_DATE,
            session_time=time(10, 0),
            type_train_id=OTHER_PERSONAL_TRAIN_ID,
        )
        assert prepaid.remaining_sessions(client["phone"], PERSONAL_TRAIN_ID) == 10

    def test_same_type_after_package_increases_used(
        self, prepaid, make_client, make_schedule, db_conn
    ):
        client = make_client(phone=9201112306)
        prepaid.add_package(client["phone"], PERSONAL_TRAIN_ID, 1000, 10)
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE main.accounting SET created_at = %s WHERE client_id = %s",
                (datetime(2020, 1, 1), client["phone"]),
            )
        db_conn.commit()
        make_schedule(
            client=client["phone"],
            session_date=SESSION_DATE,
            session_time=time(10, 0),
            type_train_id=PERSONAL_TRAIN_ID,
        )
        assert prepaid.remaining_sessions(client["phone"], PERSONAL_TRAIN_ID) == 9

    def test_session_older_than_package_not_counted(
        self, prepaid, make_client, make_schedule, make_accounting
    ):
        client = make_client(phone=9201112307)
        make_schedule(
            client=client["phone"],
            session_date=SESSION_DATE,
            session_time=time(10, 0),
            type_train_id=PERSONAL_TRAIN_ID,
        )
        make_accounting(
            client_id=client["phone"],
            type_train_id=PERSONAL_TRAIN_ID,
            summ=1000,
            count_train=10,
            price_per_train=100,
            created_at=datetime.now() + timedelta(days=1),
        )
        assert prepaid.remaining_sessions(client["phone"], PERSONAL_TRAIN_ID) == 10
