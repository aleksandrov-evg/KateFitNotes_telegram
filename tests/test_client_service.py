"""Автотесты ClientService: валидация, уникальность, списки.

Не импортирует bot.py и sql.py.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from psycopg2.errors import UniqueViolation

from src.Kate_Fit_Notes.repository import PostgresRepository
from src.Kate_Fit_Notes.services.clients import ClientService
from src.Kate_Fit_Notes.services.errors import DuplicateClientError, InvalidPhoneError


class FakeClientRepo:
    def __init__(self):
        self.clients: dict[int, dict] = {}
        self.insert_calls: list[tuple] = []
        self.raise_on_insert: Exception | None = None

    def search_client(self, phone_number):
        row = self.clients.get(phone_number)
        return [dict(row)] if row else []

    def insert_client_data(self, phone_number, name="None", surname="None"):
        self.insert_calls.append((phone_number, name, surname))
        if self.raise_on_insert is not None:
            raise self.raise_on_insert
        if phone_number in self.clients:
            raise UniqueViolation("duplicate key")
        client_id = len(self.clients) + 1
        self.clients[phone_number] = {
            "id": client_id,
            "phone": phone_number,
            "name": name,
            "surname": surname,
        }
        return client_id

    def show_all_clients(self):
        return []

    def select_last_client(self, number_client=0):
        return []


@pytest.fixture
def repo(migrated_database, db_conn):
    repository = PostgresRepository.from_dsn(migrated_database)
    try:
        yield repository
    finally:
        repository.close()


@pytest.fixture
def service(repo):
    return ClientService(repo)


class TestCreateNormalizedPhone:
    def test_plus7_inserts_ten_digits(self):
        fake = FakeClientRepo()
        ClientService(fake).create("+79001112233", "Анна", "Иванова")
        assert fake.insert_calls == [(9001112233, "Анна", "Иванова")]

    def test_eight_prefix_inserts_ten_digits(self):
        fake = FakeClientRepo()
        ClientService(fake).create("89001112233", "Анна", "Иванова")
        assert fake.insert_calls[0][0] == 9001112233


class TestCreateValidation:
    def test_invalid_phone_does_not_insert(self):
        fake = FakeClientRepo()
        with pytest.raises(InvalidPhoneError):
            ClientService(fake).create("мусор", "Анна", "Иванова")
        assert fake.insert_calls == []

    def test_none_phone_does_not_insert(self):
        fake = FakeClientRepo()
        with pytest.raises(InvalidPhoneError):
            ClientService(fake).create(None, "Анна", "Иванова")
        assert fake.insert_calls == []


class TestCreateDuplicate:
    def test_existing_phone_raises_before_insert(self):
        fake = FakeClientRepo()
        fake.clients[9001112233] = {
            "phone": 9001112233,
            "name": "Анна",
            "surname": "Иванова",
        }
        with pytest.raises(DuplicateClientError):
            ClientService(fake).create("89001112233", "Другая", "Фамилия")
        assert fake.insert_calls == []

    def test_unique_violation_mapped_to_duplicate(self):
        fake = FakeClientRepo()
        fake.raise_on_insert = UniqueViolation("duplicate key")
        with pytest.raises(DuplicateClientError):
            ClientService(fake).create("89001112233", "Анна", "Иванова")


class TestFindByPhone:
    def test_invalid_phone_is_validation_not_missing(self):
        fake = FakeClientRepo()
        with pytest.raises(InvalidPhoneError):
            ClientService(fake).find_by_phone("123")

    def test_missing_returns_none(self):
        fake = FakeClientRepo()
        assert ClientService(fake).find_by_phone("89001112233") is None

    def test_found_returns_row(self):
        fake = FakeClientRepo()
        fake.clients[9001112233] = {
            "phone": 9001112233,
            "name": "Анна",
            "surname": "Иванова",
        }
        row = ClientService(fake).find_by_phone("+79001112233")
        assert row["name"] == "Анна"


class TestCreateIntegration:
    def test_creates_normalized_row(self, service, db_conn):
        created = service.create("+79120001111", "Мария", "Петрова")
        assert created["phone"] == 9120001111
        assert created["id"] is not None
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, phone, name, surname FROM main.client WHERE phone = %s",
                (9120001111,),
            )
            row = cur.fetchone()
        assert row[0] == created["id"]
        assert row[1:] == (9120001111, "Мария", "Петрова")

    def test_duplicate_phone_does_not_insert_second_row(self, service, make_client, db_conn):
        make_client(phone=9120002222, name="Уже", surname="Есть")
        with pytest.raises(DuplicateClientError):
            service.create("89120002222", "Другая", "Фамилия")
        with db_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM main.client WHERE phone = %s", (9120002222,))
            assert cur.fetchone()[0] == 1

    def test_invalid_phone_leaves_table_empty(self, service, db_conn):
        with pytest.raises(InvalidPhoneError):
            service.create("не номер", "Анна", "Иванова")
        with db_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM main.client")
            assert cur.fetchone()[0] == 0

    def test_telegram_none_surname_stored_as_none_string(self, service, db_conn):
        service.create("79120003333", "Ольга", None)
        with db_conn.cursor() as cur:
            cur.execute("SELECT surname FROM main.client WHERE phone = %s", (9120003333,))
            assert cur.fetchone()[0] == "None"


class TestListAll:
    def test_order_by_add_time_and_fields(self, service, make_client):
        first = make_client(
            phone=9110000001,
            name="Первая",
            surname="А",
            add_time=date(2024, 1, 1),
        )
        second = make_client(
            phone=9110000002,
            name="Вторая",
            surname="Б",
            add_time=date(2024, 1, 2),
        )
        third = make_client(
            phone=9110000003,
            name="Третья",
            surname="В",
            add_time=date(2024, 1, 3),
        )
        rows = service.list_all()
        assert [row["name"] for row in rows] == ["Первая", "Вторая", "Третья"]
        assert [row["phone"] for row in rows] == [9110000001, 9110000002, 9110000003]
        assert [row["client"] for row in rows] == [first["id"], second["id"], third["id"]]
        assert "callback" not in rows[0]


class TestListRecent:
    def test_client_with_later_session_comes_first(
        self, service, make_client, make_schedule
    ):
        older = make_client(phone=9130000001, name="Раньше")
        newer = make_client(phone=9130000002, name="Позже")
        make_client(phone=9130000003, name="Без занятий")
        make_schedule(
            client_id=older["id"],
            session_date=date(2024, 5, 1),
            session_time=time(10, 0),
        )
        make_schedule(
            client_id=newer["id"],
            session_date=date(2024, 6, 1),
            session_time=time(11, 0),
        )
        rows = service.list_recent()
        assert [row["client"] for row in rows] == [newer["id"], older["id"]]
        assert [row["name"] for row in rows] == ["Позже", "Раньше"]

    def test_group_participant_appears_in_recent(self, service, make_client, make_schedule):
        visitor = make_client(phone=9130000010, name="Группа")
        make_schedule(
            client_id=None,
            session_date=date(2024, 7, 1),
            session_time=time(12, 0),
            is_group=True,
            participants=[visitor["id"]],
        )
        rows = service.list_recent()
        assert [row["client"] for row in rows] == [visitor["id"]]

    def test_phone_update_keeps_history(
        self, service, make_client, make_schedule, make_accounting, db_conn
    ):
        client = make_client(phone=9130000020, name="Смена")
        session = make_schedule(client_id=client["id"], session_date=date(2024, 8, 1))
        package = make_accounting(client_id=client["id"], type_train_id=1)
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE main.client SET phone = %s WHERE id = %s",
                (9990001111, client["id"]),
            )
        db_conn.commit()
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT client_id FROM main.schedule_participant WHERE schedule_id = %s",
                (session["id"],),
            )
            assert cur.fetchone()[0] == client["id"]
            cur.execute(
                "SELECT client_id FROM main.accounting WHERE id = %s",
                (package["id"],),
            )
            assert cur.fetchone()[0] == client["id"]
            cur.execute("SELECT phone FROM main.client WHERE id = %s", (client["id"],))
            assert cur.fetchone()[0] == 9990001111
        found = service.find_by_phone("89990001111")
        assert found["id"] == client["id"]
