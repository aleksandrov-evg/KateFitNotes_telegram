"""Негатив: прод-БД отвергается до connect."""

import pytest

from tests.db_guard import ProdDatabaseError, assert_safe_database_url, get_database_url


def test_rejects_prod_database_name():
    with pytest.raises(ProdDatabaseError, match="Kate_fitness"):
        assert_safe_database_url("postgresql://u:p@localhost:5433/Kate_fitness")


def test_rejects_prod_port():
    with pytest.raises(ProdDatabaseError, match="порт 5432"):
        assert_safe_database_url(
            "postgresql://u:p@localhost:5432/Kate_fitness_test"
        )


def test_rejects_default_port_without_explicit_port():
    with pytest.raises(ProdDatabaseError, match="порт 5432"):
        assert_safe_database_url("postgresql://u:p@localhost/Kate_fitness_test")


def test_rejects_name_without_test_suffix():
    with pytest.raises(ProdDatabaseError, match="_test"):
        assert_safe_database_url("postgresql://u:p@localhost:5433/postgres")


def test_accepts_test_url():
    target = assert_safe_database_url(
        "postgresql://u:p@localhost:5433/Kate_fitness_test"
    )
    assert target.dbname == "Kate_fitness_test"
    assert target.port == 5433


def test_missing_url_is_empty(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    assert get_database_url() is None
