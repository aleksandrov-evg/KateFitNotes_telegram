"""Проверка, что тесты не подключаются к прод-БД.

Правила этапа 0:
- нет URL → вызывающий код должен skip (не connect);
- имя БД Kate_fitness или порт 5432 → ошибка до connect;
- разрешено имя, оканчивающееся на _test, порт не 5432.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse


PROD_DATABASE_NAME = "Kate_fitness"
PROD_PORT = 5432
TEST_NAME_SUFFIX = "_test"
DBNAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ProdDatabaseError(Exception):
    """URL указывает на прод-БД — подключаться нельзя."""


@dataclass(frozen=True)
class DatabaseTarget:
    url: str
    host: str
    port: int
    dbname: str


def get_database_url() -> str | None:
    url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if url is None:
        return None
    url = url.strip()
    return url or None


def parse_database_url(url: str) -> DatabaseTarget:
    parsed = urlparse(url)
    dbname = (parsed.path or "").lstrip("/")
    if not parsed.hostname or not dbname:
        raise ProdDatabaseError(f"Некорректный DATABASE_URL: {url!r}")
    if not DBNAME_RE.fullmatch(dbname):
        raise ProdDatabaseError(f"Некорректное имя БД: {dbname!r}")
    port = parsed.port if parsed.port is not None else PROD_PORT
    return DatabaseTarget(url=url, host=parsed.hostname, port=port, dbname=dbname)


def assert_safe_database_url(url: str) -> DatabaseTarget:
    """Проверяет URL без подключения. Бросает ProdDatabaseError для прода."""
    target = parse_database_url(url)
    reasons = []
    if target.dbname == PROD_DATABASE_NAME:
        reasons.append(f"имя БД {target.dbname!r} — прод")
    if target.port == PROD_PORT:
        reasons.append(f"порт {target.port} — прод")
    if not target.dbname.endswith(TEST_NAME_SUFFIX):
        reasons.append(
            f"имя БД {target.dbname!r} должно оканчиваться на {TEST_NAME_SUFFIX!r}"
        )
    if reasons:
        raise ProdDatabaseError(
            "Отказ подключаться к подозрительной БД: "
            + "; ".join(reasons)
            + f" (url host={target.host})"
        )
    return target
