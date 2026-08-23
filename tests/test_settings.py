"""Загрузка конфига: env, fallback ini, ошибка без обязательных полей.

Не импортирует bot.py / sql.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.Kate_Fit_Notes.settings import ConfigError, load_settings

FULL_ENV = {
    "TG_TOKEN": "token-from-env",
    "TG_ACCOUNT": "user-env",
    "TG_PASS": "pass-env",
    "SQL_DATABASE": "db-env",
    "SQL_HOST": "host-env",
    "SQL_PORT": "5433",
}

INI_TEXT = """\
[main]
TOKEN=token-from-ini

[sql]
database=db-ini
user=user-ini
password=pass-ini
host=host-ini
port=5432
"""


def _write_ini(tmp_path: Path) -> Path:
    path = tmp_path / "config.ini"
    path.write_text(INI_TEXT, encoding="utf-8")
    return path


class TestLoadSettingsFromEnv:
    def test_reads_env_without_ini(self, tmp_path: Path):
        missing_ini = tmp_path / "no-such.ini"
        settings = load_settings(environ=FULL_ENV, ini_path=missing_ini)
        assert settings.telegram_token == "token-from-env"
        assert settings.sql_user == "user-env"
        assert settings.sql_password == "pass-env"
        assert settings.sql_database == "db-env"
        assert settings.sql_host == "host-env"
        assert settings.sql_port == 5433

    def test_env_wins_over_ini(self, tmp_path: Path):
        ini = _write_ini(tmp_path)
        settings = load_settings(environ=FULL_ENV, ini_path=ini)
        assert settings.telegram_token == "token-from-env"
        assert settings.sql_database == "db-env"
        assert settings.sql_port == 5433
        assert settings.telegram_token != "token-from-ini"


class TestLoadSettingsIniFallback:
    def test_reads_ini_when_env_empty(self, tmp_path: Path):
        ini = _write_ini(tmp_path)
        settings = load_settings(environ={}, ini_path=ini)
        assert settings.telegram_token == "token-from-ini"
        assert settings.sql_user == "user-ini"
        assert settings.sql_password == "pass-ini"
        assert settings.sql_database == "db-ini"
        assert settings.sql_host == "host-ini"
        assert settings.sql_port == 5432

    def test_partial_env_fills_from_ini(self, tmp_path: Path):
        ini = _write_ini(tmp_path)
        settings = load_settings(
            environ={"TG_TOKEN": "only-token-env"},
            ini_path=ini,
        )
        assert settings.telegram_token == "only-token-env"
        assert settings.sql_host == "host-ini"

    def test_empty_host_from_ini_is_error(self, tmp_path: Path):
        path = tmp_path / "config.ini"
        path.write_text(
            "[main]\nTOKEN=t\n\n"
            "[sql]\ndatabase=db\nuser=u\npassword=p\nhost=\nport=5432\n",
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="SQL_HOST"):
            load_settings(environ={}, ini_path=path)


class TestLoadSettingsErrors:
    def test_missing_required_fields(self, tmp_path: Path):
        missing_ini = tmp_path / "no-such.ini"
        with pytest.raises(ConfigError, match="обязательных"):
            load_settings(environ={}, ini_path=missing_ini)

    def test_missing_token_only(self, tmp_path: Path):
        env = {k: v for k, v in FULL_ENV.items() if k != "TG_TOKEN"}
        with pytest.raises(ConfigError, match="TG_TOKEN"):
            load_settings(environ=env, ini_path=tmp_path / "no-such.ini")

    def test_invalid_port(self, tmp_path: Path):
        env = {**FULL_ENV, "SQL_PORT": "abc"}
        with pytest.raises(ConfigError, match="SQL_PORT"):
            load_settings(environ=env, ini_path=tmp_path / "no-such.ini")
