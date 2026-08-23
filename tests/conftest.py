"""Фикстуры тестовой БД: DATABASE_URL, миграции Alembic, truncate, фабрики.

Не импортирует bot.py и sql.py. Тесты адаптера (tests/test_bot.py) импортируют bot
после этапа 10: import не вызывает load_settings и не стартует polling.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg2
import pytest
from alembic import command
from alembic.config import Config

from tests import factories
from tests.db_guard import assert_safe_database_url, get_database_url
from tests.seed import seed_trains, truncate_main

ROOT = Path(__file__).resolve().parents[1]


def _admin_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path="/postgres"))


def _create_database_if_missing(url: str, dbname: str) -> None:
    """Если том уже инициализирован без POSTGRES_DB, создаём Kate_fitness_test вручную."""
    admin = psycopg2.connect(_admin_url(url))
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        admin.close()


def _run_migrations(url: str) -> None:
    """Пересоздаём schema main: ревизия 0001 переписана по дампу, тот же revision id."""
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS main CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.alembic_version")
    finally:
        conn.close()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def database_url():
    url = get_database_url()
    if not url:
        pytest.skip("DATABASE_URL не задан — DB-тесты пропущены")
    assert_safe_database_url(url)
    return url


@pytest.fixture(scope="session")
def migrated_database(database_url, monkeypatch_session):
    target = assert_safe_database_url(database_url)
    monkeypatch_session.setenv("DATABASE_URL", database_url)
    _create_database_if_missing(database_url, target.dbname)
    _run_migrations(database_url)
    return database_url


@pytest.fixture(scope="session")
def monkeypatch_session():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture
def db_conn(migrated_database):
    conn = psycopg2.connect(migrated_database)
    try:
        truncate_main(conn)
        seed_trains(conn)
        yield conn
    finally:
        conn.close()


@pytest.fixture
def make_client(db_conn):
    def _make(**kwargs):
        return factories.make_client(db_conn, **kwargs)

    return _make


@pytest.fixture
def make_train(db_conn):
    def _make(**kwargs):
        return factories.make_train(db_conn, **kwargs)

    return _make


@pytest.fixture
def make_schedule(db_conn):
    def _make(**kwargs):
        return factories.make_schedule(db_conn, **kwargs)

    return _make


@pytest.fixture
def make_accounting(db_conn):
    def _make(**kwargs):
        return factories.make_accounting(db_conn, **kwargs)

    return _make
