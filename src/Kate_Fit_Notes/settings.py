"""Загрузка конфига: env, затем локальный config.ini. Без Telegram и БД."""

from __future__ import annotations

import configparser
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_INI_PATH = Path("config.ini")

ENV_TOKEN = "TG_TOKEN"
ENV_SQL_USER = "TG_ACCOUNT"
ENV_SQL_PASSWORD = "TG_PASS"
ENV_SQL_DATABASE = "SQL_DATABASE"
ENV_SQL_HOST = "SQL_HOST"
ENV_SQL_PORT = "SQL_PORT"


class ConfigError(ValueError):
    """Нет обязательного поля конфига."""


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    sql_user: str
    sql_password: str
    sql_database: str
    sql_host: str
    sql_port: int


def _env_value(env: Mapping[str, str], key: str) -> str | None:
    raw = env.get(key)
    if raw is None:
        return None
    stripped = str(raw).strip()
    return stripped or None


def _ini_value(
    parser: configparser.ConfigParser | None,
    section: str,
    key: str,
) -> str | None:
    if parser is None or not parser.has_option(section, key):
        return None
    return parser.get(section, key)


def _pick(
    env_val: str | None,
    ini_val: str | None,
    *,
    allow_empty: bool = False,
) -> str | None:
    if env_val is not None:
        return env_val
    if ini_val is None:
        return None
    stripped = ini_val.strip()
    if stripped:
        return stripped
    return "" if allow_empty else None


def _read_ini(ini_path: Path) -> configparser.ConfigParser | None:
    if not ini_path.is_file():
        return None
    parser = configparser.ConfigParser()
    parser.read(ini_path, encoding="utf-8")
    return parser


def load_settings(
    environ: Mapping[str, str] | None = None,
    ini_path: str | Path | None = None,
) -> Settings:
    """Env побеждает ini. Нет файла ini — не ошибка, если env полный."""
    env = os.environ if environ is None else environ
    path = DEFAULT_INI_PATH if ini_path is None else Path(ini_path)
    parser = _read_ini(path)

    token = _pick(
        _env_value(env, ENV_TOKEN),
        _ini_value(parser, "main", "TOKEN"),
    )
    sql_user = _pick(
        _env_value(env, ENV_SQL_USER),
        _ini_value(parser, "sql", "user"),
    )
    sql_password = _pick(
        _env_value(env, ENV_SQL_PASSWORD),
        _ini_value(parser, "sql", "password"),
    )
    sql_database = _pick(
        _env_value(env, ENV_SQL_DATABASE),
        _ini_value(parser, "sql", "database"),
    )
    sql_host = _pick(
        _env_value(env, ENV_SQL_HOST),
        _ini_value(parser, "sql", "host"),
    )
    sql_port_raw = _pick(
        _env_value(env, ENV_SQL_PORT),
        _ini_value(parser, "sql", "port"),
    )

    missing: list[str] = []
    if not token:
        missing.append("TG_TOKEN / [main] TOKEN")
    if not sql_user:
        missing.append("TG_ACCOUNT / [sql] user")
    if not sql_password:
        missing.append("TG_PASS / [sql] password")
    if not sql_database:
        missing.append("SQL_DATABASE / [sql] database")
    if not sql_host:
        missing.append("SQL_HOST / [sql] host")
    if not sql_port_raw:
        missing.append("SQL_PORT / [sql] port")
    if missing:
        raise ConfigError(
            "Нет обязательных полей конфига: " + ", ".join(missing)
        )

    try:
        sql_port = int(sql_port_raw)
    except ValueError as exc:
        raise ConfigError(f"SQL_PORT должен быть целым числом, не {sql_port_raw!r}") from exc

    return Settings(
        telegram_token=token,
        sql_user=sql_user,
        sql_password=sql_password,
        sql_database=sql_database,
        sql_host=sql_host,
        sql_port=sql_port,
    )
