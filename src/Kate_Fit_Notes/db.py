"""Пул и контекст соединений PostgreSQL. Без load_settings при импорте."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from psycopg2.pool import ThreadedConnectionPool

from src.Kate_Fit_Notes.settings import Settings

POOL_MINCONN = 1
POOL_MAXCONN = 5


class ConnectionPool:
    """Пул psycopg2: getconn → commit/rollback → putconn."""

    def __init__(self, minconn: int = POOL_MINCONN, maxconn: int = POOL_MAXCONN, **connect_kw):
        self._pool = ThreadedConnectionPool(minconn, maxconn, **connect_kw)

    @classmethod
    def from_settings(cls, settings: Settings) -> ConnectionPool:
        return cls(
            dbname=settings.sql_database,
            user=settings.sql_user,
            password=settings.sql_password,
            host=settings.sql_host,
            port=settings.sql_port,
        )

    @classmethod
    def from_dsn(cls, dsn: str) -> ConnectionPool:
        return cls(dsn=dsn)

    @contextmanager
    def connection(self) -> Iterator:
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    @property
    def used_count(self) -> int:
        return len(self._pool._used)

    def close(self) -> None:
        self._pool.closeall()
