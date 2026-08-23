"""Автотесты BookingService: слот, предоплата, участники.

Не импортирует bot.py и sql.py.
"""

from __future__ import annotations

import inspect
from datetime import date, time

import pytest
from psycopg2.errors import UniqueViolation

from src.Kate_Fit_Notes.repository import PostgresRepository
from src.Kate_Fit_Notes.services.booking import BookingService
from src.Kate_Fit_Notes.services.errors import (
    EmptyParticipantsError,
    InvalidTrainTypeError,
    MultiplePrepaidError,
    SlotTakenError,
)

PERSONAL_TRAIN_ID = 1
GROUP_TRAIN_ID = 2
SESSION_DATE = date(2026, 8, 24)
SESSION_TIME = time(10, 0)


class FakeBookingRepo:
    def __init__(self):
        self.trains: dict = {
            PERSONAL_TRAIN_ID: {
                "id": PERSONAL_TRAIN_ID,
                "type_train": "силовая 1 чел",
                "group_train": False,
                "rent_debt": 1400,
            },
            GROUP_TRAIN_ID: {
                "id": GROUP_TRAIN_ID,
                "type_train": "силовая 2 чел",
                "group_train": True,
                "rent_debt": 2100,
            },
        }
        self.occupied: dict = {}
        self.insert_calls: list[tuple] = []
        self.prepaid: list[dict] = []
        self.last_prices: list[dict] = []
        self.usage: list[dict] = []
        self.raise_on_insert: Exception | None = None
        self.schedule_rows: list[dict] = []

    def get_train(self, train_id):
        return self.trains.get(train_id)

    def list_all_train(self, group):
        return [
            dict(row)
            for row in self.trains.values()
            if bool(row.get("group_train")) is bool(group)
        ]

    def select_time_at_data(self, session_date):
        return list(self.occupied.get(session_date, []))

    def insert_in_schedule(
        self,
        date,
        client_id,
        participant_ids,
        time,
        rent_debt,
        type_train,
        is_group,
        train_price,
        type_train_id,
        set_is_complete_true=False,
        accounting_id=None,
    ):
        if self.raise_on_insert is not None:
            raise self.raise_on_insert
        self.insert_calls.append(
            (
                date,
                client_id,
                list(participant_ids or []),
                time,
                rent_debt,
                type_train,
                is_group,
                train_price,
                type_train_id,
                set_is_complete_true,
                accounting_id,
            )
        )
        self.occupied.setdefault(date, []).append(time)
        schedule_id = len(self.schedule_rows) + 1
        self.schedule_rows.append(
            {
                "id": schedule_id,
                "date": date,
                "time": time,
                "client_id": client_id,
                "participant_ids": list(participant_ids or []),
                "is_group": is_group,
                "price": train_price,
                "type_train_id": type_train_id,
                "accounting_id": accounting_id,
            }
        )

    def get_schedule_at(self, date, time):
        for row in reversed(self.schedule_rows):
            if row["date"] == date and row["time"] == time:
                return row
        return None

    def get_schedule_participants(self, schedule_id):
        for row in self.schedule_rows:
            if row["id"] == schedule_id:
                return list(row.get("participant_ids") or [])
        return []

    def get_active_prepaid_for_client(self, client_id, type_train_id):
        return list(self.prepaid)

    def get_count_prepaid_train(self, client_id, type_train_id):
        return list(self.usage)

    def get_last_price_for_train(self, client_id, type_train_id):
        return list(self.last_prices)


@pytest.fixture
def repo(migrated_database, db_conn):
    repository = PostgresRepository.from_dsn(migrated_database)
    try:
        yield repository
    finally:
        repository.close()


@pytest.fixture
def service(repo):
    return BookingService(repo)


class TestBookPersonalUnit:
    def test_occupies_slot_without_client_multi(self):
        fake = FakeBookingRepo()
        result = BookingService(fake).book_personal(
            42,
            PERSONAL_TRAIN_ID,
            SESSION_DATE,
            SESSION_TIME,
            price=1000,
        )
        assert result["client"] == 42
        assert fake.insert_calls[0][1] == 42
        assert fake.insert_calls[0][2] == [42]
        assert fake.insert_calls[0][6] is False
        assert "client_multi" not in inspect.signature(BookingService.book_personal).parameters
        assert SESSION_TIME not in BookingService(fake).list_available_slots(SESSION_DATE)

    def test_repeat_same_datetime_refused(self):
        fake = FakeBookingRepo()
        service = BookingService(fake)
        service.book_personal(42, PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000)
        with pytest.raises(SlotTakenError):
            service.book_personal(
                43, PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1200
            )
        assert len(fake.insert_calls) == 1

    def test_unique_violation_mapped_to_slot_taken(self):
        fake = FakeBookingRepo()
        fake.raise_on_insert = UniqueViolation("duplicate key")
        with pytest.raises(SlotTakenError):
            BookingService(fake).book_personal(
                42, PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000
            )

    def test_group_train_refused(self):
        fake = FakeBookingRepo()
        with pytest.raises(InvalidTrainTypeError):
            BookingService(fake).book_personal(
                42, GROUP_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000
            )
        assert fake.insert_calls == []

    def test_prepaid_price_substituted_when_one_package(self):
        fake = FakeBookingRepo()
        fake.prepaid = [
            {"id": 11, "price_per_train": 1500, "count_train": 10},
        ]
        BookingService(fake).book_personal(
            42, PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=None
        )
        assert fake.insert_calls[0][7] == 1500
        assert fake.insert_calls[0][10] == 11

    def test_multiple_prepaid_refused(self):
        fake = FakeBookingRepo()
        fake.prepaid = [
            {"id": 11, "price_per_train": 1500, "count_train": 10},
            {"id": 12, "price_per_train": 1600, "count_train": 8},
        ]
        with pytest.raises(MultiplePrepaidError) as exc:
            BookingService(fake).book_personal(
                42, PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000
            )
        assert exc.value.count == 2
        assert fake.insert_calls == []


class TestSuggestPriceUnit:
    def test_one_package_returns_prepaid_price(self):
        fake = FakeBookingRepo()
        fake.prepaid = [{"id": 11, "price_per_train": 1500, "count_train": 10}]
        hint = BookingService(fake).suggest_personal_price(42, PERSONAL_TRAIN_ID)
        assert hint.prepaid_price == 1500
        assert hint.last_prices == []

    def test_no_package_returns_last_prices(self):
        fake = FakeBookingRepo()
        fake.last_prices = [{"price": 900}]
        hint = BookingService(fake).suggest_personal_price(42, PERSONAL_TRAIN_ID)
        assert hint.prepaid_price is None
        assert hint.last_prices == [{"price": 900}]

    def test_multiple_packages_raise(self):
        fake = FakeBookingRepo()
        fake.prepaid = [
            {"id": 11, "price_per_train": 1500},
            {"id": 12, "price_per_train": 1600},
        ]
        with pytest.raises(MultiplePrepaidError):
            BookingService(fake).suggest_personal_price(42, PERSONAL_TRAIN_ID)


class TestAvailableSlotsUnit:
    def test_occupied_hour_missing(self):
        fake = FakeBookingRepo()
        fake.occupied[SESSION_DATE] = [time(10, 0)]
        slots = BookingService(fake).list_available_slots(SESSION_DATE)
        assert time(10, 0) not in slots
        assert time(9, 0) in slots


class TestListTrainTypesUnit:
    def test_personal_and_group_filtered(self):
        fake = FakeBookingRepo()
        personal = BookingService(fake).list_train_types(False)
        group = BookingService(fake).list_train_types(True)
        assert [row["id"] for row in personal] == [PERSONAL_TRAIN_ID]
        assert [row["id"] for row in group] == [GROUP_TRAIN_ID]


class TestBookPersonalIntegration:
    def test_occupies_slot(self, service, make_client, db_conn):
        client = make_client(phone=9201112233)
        service.book_personal(
            client["id"], PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT client_id, time, price, is_group "
                "FROM main.schedule WHERE date = %s AND client_id = %s",
                (SESSION_DATE, client["id"]),
            )
            row = cur.fetchone()
            cur.execute(
                "SELECT client_id FROM main.schedule_participant "
                "WHERE schedule_id = (SELECT id FROM main.schedule "
                "WHERE date = %s AND client_id = %s)",
                (SESSION_DATE, client["id"]),
            )
            participants = [item[0] for item in cur.fetchall()]
        assert row[0] == client["id"]
        assert row[1] == SESSION_TIME
        assert row[2] == 1000
        assert row[3] is False
        assert participants == [client["id"]]

    def test_repeat_same_datetime_refused(self, service, make_client, db_conn):
        first = make_client(phone=9201112234)
        second = make_client(phone=9201112235)
        service.book_personal(
            first["id"], PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000
        )
        with pytest.raises(SlotTakenError):
            service.book_personal(
                second["id"], PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1200
            )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM main.schedule WHERE date = %s AND time = %s",
                (SESSION_DATE, SESSION_TIME),
            )
            assert cur.fetchone()[0] == 1

    def test_prepaid_price_when_one_package(
        self, service, make_client, make_accounting, db_conn
    ):
        client = make_client(phone=9201112236)
        package = make_accounting(
            client_id=client["id"],
            type_train_id=PERSONAL_TRAIN_ID,
            price_per_train=1500,
            count_train=10,
        )
        service.book_personal(
            client["id"], PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=None
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT price, accounting_id FROM main.schedule WHERE client_id = %s",
                (client["id"],),
            )
            row = cur.fetchone()
        assert row[0] == 1500
        assert row[1] == package["id"]

    def test_occupied_hour_not_in_available_slots(
        self, service, make_client, make_schedule
    ):
        client = make_client(phone=9201112237)
        make_schedule(
            client_id=client["id"],
            session_date=SESSION_DATE,
            session_time=SESSION_TIME,
            type_train_id=PERSONAL_TRAIN_ID,
        )
        slots = service.list_available_slots(SESSION_DATE)
        assert SESSION_TIME not in slots
        assert time(11, 0) in slots

    def test_does_not_require_client_multi(self, service, make_client):
        client = make_client(phone=9201112238)
        service.book_personal(
            client["id"], PERSONAL_TRAIN_ID, SESSION_DATE, time(12, 0), price=800
        )
        assert "client_multi" not in inspect.signature(service.book_personal).parameters


class TestBookGroupUnit:
    def test_writes_participants_without_group_stub(self):
        fake = FakeBookingRepo()
        result = BookingService(fake).book_group(
            [42, 43],
            GROUP_TRAIN_ID,
            SESSION_DATE,
            SESSION_TIME,
            price=2000,
        )
        assert result["client"] is None
        assert result["participants"] == [42, 43]
        assert fake.insert_calls[0][1] is None
        assert fake.insert_calls[0][2] == [42, 43]
        assert fake.insert_calls[0][6] is True

    def test_empty_list_refused_no_insert(self):
        fake = FakeBookingRepo()
        with pytest.raises(EmptyParticipantsError):
            BookingService(fake).book_group(
                [], GROUP_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=2000
            )
        with pytest.raises(EmptyParticipantsError):
            BookingService(fake).book_group(
                None, GROUP_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=2000
            )
        assert fake.insert_calls == []

    def test_personal_train_refused(self):
        fake = FakeBookingRepo()
        with pytest.raises(InvalidTrainTypeError):
            BookingService(fake).book_group(
                [42], PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=2000
            )
        assert fake.insert_calls == []

    def test_slot_taken_after_group(self):
        fake = FakeBookingRepo()
        service = BookingService(fake)
        service.book_group(
            [42, 43],
            GROUP_TRAIN_ID,
            SESSION_DATE,
            SESSION_TIME,
            price=2000,
        )
        with pytest.raises(SlotTakenError):
            service.book_personal(
                44, PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000
            )
        assert len(fake.insert_calls) == 1


class TestBookGroupIntegration:
    def test_participants_roundtrip(self, service, make_client, db_conn):
        first = make_client(phone=9201112240)
        second = make_client(phone=9201112241)
        result = service.book_group(
            [first["id"], second["id"]],
            GROUP_TRAIN_ID,
            SESSION_DATE,
            SESSION_TIME,
            price=2000,
        )
        assert result["client"] is None
        assert result["participants"] == sorted([first["id"], second["id"]])
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT client_id, is_group, price "
                "FROM main.schedule WHERE date = %s AND time = %s",
                (SESSION_DATE, SESSION_TIME),
            )
            row = cur.fetchone()
            cur.execute(
                "SELECT client_id FROM main.schedule_participant "
                "WHERE schedule_id = (SELECT id FROM main.schedule "
                "WHERE date = %s AND time = %s) "
                "ORDER BY client_id",
                (SESSION_DATE, SESSION_TIME),
            )
            participants = [item[0] for item in cur.fetchall()]
        assert row[0] is None
        assert row[1] is True
        assert row[2] == 2000
        assert participants == sorted([first["id"], second["id"]])

    def test_empty_list_does_not_occupy_slot(self, service, db_conn):
        with pytest.raises(EmptyParticipantsError):
            service.book_group(
                [], GROUP_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=2000
            )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM main.schedule WHERE date = %s AND time = %s",
                (SESSION_DATE, SESSION_TIME),
            )
            assert cur.fetchone()[0] == 0

    def test_personal_after_group_same_slot_refused(
        self, service, make_client, db_conn
    ):
        first = make_client(phone=9201112242)
        second = make_client(phone=9201112243)
        personal = make_client(phone=9201112244)
        service.book_group(
            [first["id"], second["id"]],
            GROUP_TRAIN_ID,
            SESSION_DATE,
            SESSION_TIME,
            price=2000,
        )
        with pytest.raises(SlotTakenError):
            service.book_personal(
                personal["id"], PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=1000
            )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM main.schedule WHERE date = %s AND time = %s",
                (SESSION_DATE, SESSION_TIME),
            )
            assert cur.fetchone()[0] == 1

    def test_personal_train_type_refused(self, service, make_client, db_conn):
        client = make_client(phone=9201112245)
        with pytest.raises(InvalidTrainTypeError):
            service.book_group(
                [client["id"]], PERSONAL_TRAIN_ID, SESSION_DATE, SESSION_TIME, price=2000
            )
        with db_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM main.schedule")
            assert cur.fetchone()[0] == 0
