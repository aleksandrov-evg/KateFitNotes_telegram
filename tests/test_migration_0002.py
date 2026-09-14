"""Миграция 0001 → 0002: телефон-PK в surrogate id, участники, accounting_id."""

from __future__ import annotations

from datetime import date, datetime, time

import psycopg2
import pytest

from tests.conftest import alembic_upgrade, reset_schema
from tests.seed import seed_trains

PHONE_A = 9201112501
PHONE_B = 9201112502
SESSION_DATE = date(2026, 8, 20)


@pytest.fixture
def v1_database(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    reset_schema(database_url)
    alembic_upgrade(database_url, "0001_initial_as_is")
    yield database_url
    reset_schema(database_url)
    alembic_upgrade(database_url, "head")
    conn = psycopg2.connect(database_url)
    try:
        seed_trains(conn)
    finally:
        conn.close()


def test_phone_pk_migrates_to_surrogate_id(v1_database):
    conn = psycopg2.connect(v1_database)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO main.trains (type_train, id, group_train, rent_debt) "
                "VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)",
                (
                    "силовая 1 чел",
                    1,
                    False,
                    1400,
                    "силовая 2 чел",
                    2,
                    True,
                    2100,
                ),
            )
            cur.execute(
                "INSERT INTO main.client (phone, name, surname, add_time) "
                "VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)",
                (
                    PHONE_A,
                    "Анна",
                    "Первая",
                    date(2024, 1, 1),
                    PHONE_B,
                    "Борис",
                    "Второй",
                    date(2024, 1, 2),
                ),
            )
            cur.execute(
                "INSERT INTO main.accounting "
                "(client_id, summ, count_train, price_per_train, type_train_id, "
                "is_complete, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    PHONE_A,
                    10000,
                    10,
                    1000,
                    1,
                    False,
                    datetime(2020, 1, 1),
                    datetime(2020, 1, 1),
                ),
            )
            cur.execute(
                "INSERT INTO main.price (client, price, date) VALUES (%s, %s, %s)",
                (PHONE_A, 900, date(2025, 1, 1)),
            )
            cur.execute(
                "INSERT INTO main.schedule "
                "(price, spend, date, time, rent_debt, type_train, client, "
                "client_list, is_group, type_train_id, add_time) "
                "VALUES (%s, false, %s, %s, %s, %s, %s, %s, false, %s, %s)",
                (
                    1000,
                    SESSION_DATE,
                    time(10, 0),
                    1400,
                    "силовая 1 чел",
                    PHONE_A,
                    [PHONE_A],
                    1,
                    datetime(2026, 8, 20, 10, 0),
                ),
            )
            cur.execute(
                "INSERT INTO main.schedule "
                "(price, spend, date, time, rent_debt, type_train, client, "
                "client_list, is_group, type_train_id, add_time) "
                "VALUES (%s, false, %s, %s, %s, %s, %s, %s, true, %s, %s)",
                (
                    2000,
                    SESSION_DATE,
                    time(11, 0),
                    2100,
                    "силовая 2 чел",
                    -1,
                    [PHONE_A, PHONE_B],
                    2,
                    datetime(2026, 8, 20, 11, 0),
                ),
            )
    finally:
        conn.close()

    alembic_upgrade(v1_database, "head")

    conn = psycopg2.connect(v1_database)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, phone, name FROM main.client ORDER BY phone"
            )
            clients = cur.fetchall()
            assert [row[1] for row in clients] == [PHONE_A, PHONE_B]
            id_a, id_b = clients[0][0], clients[1][0]
            assert id_a != id_b

            cur.execute(
                "SELECT client_id, is_group, accounting_id "
                "FROM main.schedule WHERE time = %s",
                (time(10, 0),),
            )
            personal = cur.fetchone()
            assert personal[0] == id_a
            assert personal[1] is False
            assert personal[2] is not None

            cur.execute(
                "SELECT client_id FROM main.accounting WHERE id = %s",
                (personal[2],),
            )
            assert cur.fetchone()[0] == id_a

            cur.execute(
                "SELECT sp.client_id FROM main.schedule_participant sp "
                "JOIN main.schedule s ON s.id = sp.schedule_id "
                "WHERE s.time = %s ORDER BY sp.client_id",
                (time(10, 0),),
            )
            assert [row[0] for row in cur.fetchall()] == [id_a]

            cur.execute(
                "SELECT client_id, is_group FROM main.schedule WHERE time = %s",
                (time(11, 0),),
            )
            group = cur.fetchone()
            assert group[0] is None
            assert group[1] is True
            cur.execute(
                "SELECT sp.client_id FROM main.schedule_participant sp "
                "JOIN main.schedule s ON s.id = sp.schedule_id "
                "WHERE s.time = %s ORDER BY sp.client_id",
                (time(11, 0),),
            )
            assert [row[0] for row in cur.fetchall()] == sorted([id_a, id_b])

            cur.execute(
                "SELECT client_id FROM main.accounting WHERE client_id = %s",
                (id_a,),
            )
            assert cur.fetchone()[0] == id_a
            cur.execute(
                "SELECT client_id FROM main.price WHERE client_id = %s",
                (id_a,),
            )
            assert cur.fetchone()[0] == id_a
    finally:
        conn.close()
