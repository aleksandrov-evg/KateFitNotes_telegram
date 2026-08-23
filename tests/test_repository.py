"""Автотесты репозитория: поиск, апостроф, пул, параметризация SQL.

Не импортирует bot.py и sql.py.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.Kate_Fit_Notes.repository import PostgresRepository


class FakeCursor:
    def __init__(self):
        self.calls: list[tuple] = []
        self.statusmessage = "SELECT 0"

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class FakePool:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.putconn_called = False
        self._used = 0

    @contextmanager
    def connection(self):
        self._used += 1
        try:
            yield FakeConnection(self._cursor)
        finally:
            self._used -= 1
            self.putconn_called = True

    @property
    def used_count(self) -> int:
        return self._used


@pytest.fixture
def repo(migrated_database, db_conn):
    repository = PostgresRepository.from_dsn(migrated_database)
    try:
        yield repository
    finally:
        repository.close()


class TestSearchClient:
    def test_finds_existing_client(self, repo, make_client):
        make_client(phone=9001112233, name="Анна", surname="Иванова")
        rows = repo.search_client(9001112233)
        assert len(rows) == 1
        assert rows[0]["phone"] == 9001112233
        assert rows[0]["name"] == "Анна"

    def test_missing_client_returns_empty_list(self, repo):
        rows = repo.search_client(9000000000)
        assert rows == []


class TestInsertClientApostrophe:
    def test_name_with_apostrophe_roundtrip(self, repo):
        repo.insert_client_data(9001112244, "O'Brien", "Д'Артаньян")
        rows = repo.search_client(9001112244)
        assert len(rows) == 1
        assert rows[0]["name"] == "O'Brien"
        assert rows[0]["surname"] == "Д'Артаньян"


class TestConnectionDoesNotLeak:
    def test_pool_used_empty_after_query(self, repo, make_client):
        make_client(phone=9001112255)
        repo.search_client(9001112255)
        assert repo.pool.used_count == 0

    def test_fake_pool_returns_connection(self):
        cursor = FakeCursor()
        pool = FakePool(cursor)
        repository = PostgresRepository(pool)
        repository.search_client(9001112233)
        assert pool.used_count == 0
        assert pool.putconn_called is True


class TestSqlParametersNotInterpolated:
    def test_malicious_phone_goes_to_params(self):
        payload = "1; DROP TABLE main.client; --"
        cursor = FakeCursor()
        repository = PostgresRepository(FakePool(cursor))
        repository.search_client(payload)
        assert cursor.calls
        sql, params = cursor.calls[0]
        assert "%s" in sql
        assert "DROP TABLE" not in sql
        assert params == (payload,)

    def test_apostrophe_name_goes_to_params(self):
        cursor = FakeCursor()
        repository = PostgresRepository(FakePool(cursor))
        repository.insert_client_data(9001112266, "O'Brien", "Д'Артаньян")
        assert cursor.calls
        sql, params = cursor.calls[0]
        assert "%s" in sql
        assert "O'Brien" not in sql
        assert "Д'Артаньян" not in sql
        assert params[1] == "O'Brien"
        assert params[2] == "Д'Артаньян"
