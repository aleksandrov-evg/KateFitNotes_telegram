"""Смоук Dockerfile / compose / .env.example и регрессия логирования SQL.

Не импортирует bot.py / sql.py.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_cmd_is_python3_bot():
    text = (ROOT / "dockerfile").read_text(encoding="utf-8")
    assert "python3" in text
    assert "bot.py" in text
    assert "-m" not in text or "-m bot.py" not in text
    assert 'CMD ["python3", "bot.py"]' in text


def test_dockerfile_does_not_copy_secrets_or_broken_tests():
    text = (ROOT / "dockerfile").read_text(encoding="utf-8")
    assert "config.ini" not in text
    assert "test.py" not in text


def test_compose_uses_postgres_db_not_typo():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "POSTGRESS_DB" not in text
    assert "POSTGRES_DB: Kate_fitness" in text
    assert "POSTGRES_DB: Kate_fitness_test" in text


def test_compose_postgres_healthcheck_and_bot_waits():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "healthcheck:" in text
    assert "pg_isready" in text
    assert "condition: service_healthy" in text
    assert "TG_TOKEN: $TG_TOKEN" in text
    assert "SQL_HOST: db_pg" in text
    assert "SQL_DATABASE: Kate_fitness" in text


def test_env_example_documents_token_and_test_db():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "TG_TOKEN=" in text
    assert "SQL_DATABASE=" in text
    assert "DATABASE_URL=" in text
    assert "5433" in text
    assert "Kate_fitness_test" in text


def test_sql_py_does_not_log_full_query_with_pii():
    source = (ROOT / "sql.py").read_text(encoding="utf-8")
    assert "cursor.query" not in source
    assert "logging" in source
    assert "statusmessage" in source


def test_pytest_does_not_autoload_dotenv():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pytest_ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "pytest-dotenv" not in pyproject
    assert "env_files" not in pyproject
    assert "env_file" not in pytest_ini
    assert "addopts" not in pytest_ini or "--env" not in pytest_ini


def test_runtime_deps_split_and_no_keyboa():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "pyTelegramBotAPI" in pyproject
    assert "psycopg2-binary" in pyproject
    assert "keyboa" not in pyproject
    assert "[dependency-groups]" in pyproject
    assert "pytest" in pyproject
