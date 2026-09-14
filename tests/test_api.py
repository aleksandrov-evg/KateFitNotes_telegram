"""Контракт HTTP API. Без прод-БД и живого Telegram."""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from psycopg2.errors import UniqueViolation

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.repository import PostgresRepository
from src.Kate_Fit_Notes.settings import ConfigError, Settings

SESSION_DATE = date(2026, 8, 24)
SESSION_TIME = time(10, 0)
PERSONAL_TRAIN_ID = 1
GROUP_TRAIN_ID = 2

API_SETTINGS = Settings(
    telegram_token="test-token",
    sql_user="user",
    sql_password="pass",
    sql_database="Kate_fitness_test",
    sql_host="localhost",
    sql_port=5433,
    api_user="admin",
    api_password="secret",
    api_jwt_secret="test-jwt-secret-which-is-32-bytes!",
)


class FakeApiRepo:
    def __init__(self):
        self.clients: list[dict] = []
        self.next_id = 1
        self.insert_client_calls: list[tuple] = []
        self.insert_accounting_calls: list[tuple] = []
        self.trains = [
            {
                "id": PERSONAL_TRAIN_ID,
                "type_train": "силовая 1 чел",
                "group_train": False,
                "rent_debt": 0,
            },
            {
                "id": GROUP_TRAIN_ID,
                "type_train": "группа",
                "group_train": True,
                "rent_debt": 500,
            },
        ]
        self.occupied: dict = {}
        self.schedules: list[dict] = []
        self.active_prepaid: list[dict] = []

    def search_client(self, phone_number):
        return [dict(row) for row in self.clients if row["phone"] == phone_number]

    def insert_client_data(self, phone_number, name="None", surname="None"):
        self.insert_client_calls.append((phone_number, name, surname))
        client_id = self.next_id
        self.next_id += 1
        self.clients.append(
            {
                "id": client_id,
                "phone": phone_number,
                "name": name,
                "surname": surname,
                "add_time": date.today(),
            }
        )
        return client_id

    def get_client(self, client_id):
        for row in self.clients:
            if row["id"] == client_id:
                return dict(row)
        return None

    def list_clients(self, q, limit, offset):
        items = [dict(row) for row in self.clients]
        if q:
            needle = q.lower()
            items = [
                row
                for row in items
                if needle in str(row.get("name") or "").lower()
                or needle in str(row.get("surname") or "").lower()
                or needle in str(row.get("phone") or "")
            ]
        total = len(items)
        return {"items": items[offset : offset + limit], "total": total}

    def show_all_clients(self):
        return [
            {
                "client": row["id"],
                "name": row["name"],
                "surname": row["surname"],
                "phone": row["phone"],
            }
            for row in self.clients
        ]

    def select_last_client(self, number_client=0):
        return self.show_all_clients()

    def list_all_train(self, group):
        return [
            dict(row)
            for row in self.trains
            if bool(row.get("group_train")) is bool(group)
        ]

    def get_train(self, train_id):
        return next((dict(row) for row in self.trains if row["id"] == train_id), None)

    def select_time_at_data(self, session_date):
        return list(self.occupied.get(session_date, []))

    def get_schedule_at(self, session_date, session_time):
        for row in self.schedules:
            if row["date"] == session_date and row["time"] == session_time:
                return dict(row)
        return None

    def get_schedule_participants(self, schedule_id):
        for row in self.schedules:
            if row["id"] == schedule_id:
                return list(row.get("participants") or [])
        return []

    def insert_in_schedule(
        self,
        session_date,
        client_id,
        participant_ids,
        session_time,
        rent_debt,
        type_train,
        is_group,
        train_price,
        type_train_id,
        set_is_complete_true=False,
        accounting_id=None,
    ):
        occupied = self.occupied.setdefault(session_date, [])
        if session_time in occupied:
            raise UniqueViolation("slot taken")
        occupied.append(session_time)
        schedule_id = len(self.schedules) + 1
        self.schedules.append(
            {
                "id": schedule_id,
                "date": session_date,
                "time": session_time,
                "client_id": client_id,
                "participants": list(participant_ids or []),
                "price": train_price,
                "type_train_id": type_train_id,
                "accounting_id": accounting_id,
                "is_group": is_group,
            }
        )

    def insert_in_accounting(
        self, client_id, summ, count_train, price_per_train, type_train_id
    ):
        self.insert_accounting_calls.append(
            (client_id, summ, count_train, price_per_train, type_train_id)
        )
        self.active_prepaid.append(
            {
                "id": len(self.active_prepaid) + 1,
                "client_id": client_id,
                "summ": summ,
                "count_train": count_train,
                "price_per_train": price_per_train,
                "type_train_id": type_train_id,
            }
        )

    def get_active_prepaid_for_client(self, client_id, type_train_id):
        return [
            dict(row)
            for row in self.active_prepaid
            if row["client_id"] == client_id and row["type_train_id"] == type_train_id
        ]

    def get_count_prepaid_train(self, client_id, type_train_id):
        return []

    def get_last_price_for_train(self, client_id, type_train_id):
        return []

    def get_incom_all_month_balance(self):
        return [
            {
                "income": 1000,
                "sum_rent": 200,
                "total_sum": 1200,
                "month": date(2026, 8, 1),
            }
        ]


def make_client_app(repo=None):
    return TestClient(create_app(API_SETTINGS, repo or FakeApiRepo()))


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "secret"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_app_requires_api_credentials():
    bare = Settings(
        telegram_token="t",
        sql_user="u",
        sql_password="p",
        sql_database="db",
        sql_host="h",
        sql_port=5433,
    )
    with pytest.raises(ConfigError, match="API_USER"):
        create_app(bare, FakeApiRepo())


def test_health_without_auth():
    client = make_client_app()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_has_client_and_booking_paths():
    client = make_client_app()
    paths = client.app.openapi()["paths"]
    assert "/api/v1/clients" in paths
    assert "get" in paths["/api/v1/clients"]
    assert "post" in paths["/api/v1/clients"]
    assert "/api/v1/bookings/personal" in paths
    assert "/api/v1/bookings/group" in paths
    assert "/api/v1/prepaid" in paths
    assert "/api/v1/reports/monthly" in paths
    client_get = paths["/api/v1/clients"]["get"]
    assert "401" in client_get["responses"]
    booking_post = paths["/api/v1/bookings/personal"]["post"]
    assert "requestBody" in booking_post


def test_clients_without_token_is_401():
    client = make_client_app()
    response = client.get("/api/v1/clients")
    assert response.status_code == 401


def test_clients_with_junk_bearer_is_401():
    client = make_client_app()
    response = client.get(
        "/api/v1/clients",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_login_wrong_password_is_401():
    client = make_client_app()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


def test_create_client_contract_and_duplicate():
    repo = FakeApiRepo()
    client = make_client_app(repo)
    headers = auth_headers(client)
    created = client.post(
        "/api/v1/clients",
        headers=headers,
        json={"phone": "89001112233", "name": "Анна", "surname": "Иванова"},
    )
    assert created.status_code == 201
    body = created.json()
    assert set(body) >= {"id", "phone", "name", "surname"}
    assert body["phone"] == 9001112233
    assert body["name"] == "Анна"
    again = client.post(
        "/api/v1/clients",
        headers=headers,
        json={"phone": "89001112233", "name": "Другая", "surname": "Фамилия"},
    )
    assert again.status_code == 409
    assert len(repo.insert_client_calls) == 1


def test_invalid_phone_is_422():
    repo = FakeApiRepo()
    client = make_client_app(repo)
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/clients",
        headers=headers,
        json={"phone": "мусор", "name": "Анна"},
    )
    assert response.status_code == 422
    assert repo.insert_client_calls == []


def test_list_clients_pagination_and_search():
    repo = FakeApiRepo()
    client = make_client_app(repo)
    headers = auth_headers(client)
    client.post(
        "/api/v1/clients",
        headers=headers,
        json={"phone": "89001110001", "name": "Анна", "surname": "А"},
    )
    client.post(
        "/api/v1/clients",
        headers=headers,
        json={"phone": "89001110002", "name": "Борис", "surname": "Б"},
    )
    client.post(
        "/api/v1/clients",
        headers=headers,
        json={"phone": "89001110003", "name": "Антон", "surname": "В"},
    )
    page = client.get(
        "/api/v1/clients",
        headers=headers,
        params={"q": "Ан", "limit": 1, "offset": 0},
    )
    assert page.status_code == 200
    body = page.json()
    assert set(body) >= {"items", "total", "limit", "offset"}
    assert body["total"] == 2
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert set(body["items"][0]) >= {"id", "phone", "name", "surname"}


def test_get_missing_client_is_404():
    client = make_client_app()
    headers = auth_headers(client)
    response = client.get("/api/v1/clients/99", headers=headers)
    assert response.status_code == 404


def test_book_personal_conflict_is_409():
    repo = FakeApiRepo()
    repo.occupied[SESSION_DATE] = [SESSION_TIME]
    client = make_client_app(repo)
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/bookings/personal",
        headers=headers,
        json={
            "client_id": 42,
            "type_train_id": PERSONAL_TRAIN_ID,
            "date": SESSION_DATE.isoformat(),
            "time": "10:00:00",
            "price": 1500,
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert "detail" in body


def test_book_personal_contract():
    repo = FakeApiRepo()
    client = make_client_app(repo)
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/bookings/personal",
        headers=headers,
        json={
            "client_id": 42,
            "type_train_id": PERSONAL_TRAIN_ID,
            "date": SESSION_DATE.isoformat(),
            "time": "10:00:00",
            "price": 1500,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) >= {"client", "date", "time", "price", "type_train_id"}
    assert body["client"] == 42
    assert body["type_train_id"] == PERSONAL_TRAIN_ID


def test_prepaid_zero_count_is_422_and_not_inserted():
    repo = FakeApiRepo()
    client = make_client_app(repo)
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/prepaid",
        headers=headers,
        json={
            "client_id": 42,
            "type_train_id": PERSONAL_TRAIN_ID,
            "summ": 1000,
            "count": 0,
        },
    )
    assert response.status_code == 422
    assert repo.insert_accounting_calls == []


def test_prepaid_second_package_is_409():
    repo = FakeApiRepo()
    client = make_client_app(repo)
    headers = auth_headers(client)
    payload = {
        "client_id": 42,
        "type_train_id": PERSONAL_TRAIN_ID,
        "summ": 1000,
        "count": 10,
    }
    first = client.post("/api/v1/prepaid", headers=headers, json=payload)
    assert first.status_code == 201
    body = first.json()
    assert body["count_train"] == 10
    assert body["price_per_train"] == 100
    second = client.post("/api/v1/prepaid", headers=headers, json=payload)
    assert second.status_code == 409
    assert len(repo.insert_accounting_calls) == 1


def test_monthly_report_keys():
    client = make_client_app()
    headers = auth_headers(client)
    response = client.get("/api/v1/reports/monthly", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert set(rows[0]) >= {"income", "sum_rent", "total_sum", "month"}


class TestApiIntegration:
    @pytest.fixture
    def repo(self, migrated_database, db_conn):
        repository = PostgresRepository.from_dsn(migrated_database)
        try:
            yield repository
        finally:
            repository.close()

    @pytest.fixture
    def client(self, repo):
        return TestClient(create_app(API_SETTINGS, repo))

    def test_create_client_matches_service_invariants(self, client, db_conn):
        headers = auth_headers(client)
        created = client.post(
            "/api/v1/clients",
            headers=headers,
            json={"phone": "+79120001111", "name": "Мария", "surname": "Петрова"},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["phone"] == 9120001111
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT phone, name FROM main.client WHERE id = %s",
                (body["id"],),
            )
            row = cur.fetchone()
        assert row == (9120001111, "Мария")
        duplicate = client.post(
            "/api/v1/clients",
            headers=headers,
            json={"phone": "89120001111", "name": "Другая"},
        )
        assert duplicate.status_code == 409

    def test_prepaid_zero_leaves_no_row(self, client, make_client, db_conn):
        person = make_client(phone=9120002222)
        headers = auth_headers(client)
        response = client.post(
            "/api/v1/prepaid",
            headers=headers,
            json={
                "client_id": person["id"],
                "type_train_id": PERSONAL_TRAIN_ID,
                "summ": 1000,
                "count": 0,
            },
        )
        assert response.status_code == 422
        with db_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM main.accounting")
            assert cur.fetchone()[0] == 0

    def test_second_booking_same_slot_is_409(self, client, make_client):
        person = make_client(phone=9120003333)
        headers = auth_headers(client)
        payload = {
            "client_id": person["id"],
            "type_train_id": PERSONAL_TRAIN_ID,
            "date": SESSION_DATE.isoformat(),
            "time": "10:00:00",
            "price": 1500,
        }
        first = client.post("/api/v1/bookings/personal", headers=headers, json=payload)
        assert first.status_code == 201
        second = client.post("/api/v1/bookings/personal", headers=headers, json=payload)
        assert second.status_code == 409
