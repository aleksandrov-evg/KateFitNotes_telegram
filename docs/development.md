# Разработка

## Быстрый старт

Нужны Python 3.14, `uv`, Docker и Docker Compose v2. Создайте `.env` из
шаблона и укажите учётные данные без добавления файла в Git:

```bash
cp .env.example .env
uv sync
```

Для запуска бота локально задайте переменные из `.env` в окружении либо
используйте локальный `config.ini` как fallback:

```bash
uv run python bot.py
```

HTTP API запускается отдельно:

```bash
uv run uvicorn src.Kate_Fit_Notes.api.app:app_from_env --factory \
  --host 127.0.0.1 --port 8000
```

`import bot` не запускает polling. Это позволяет использовать `create_bot`
в тестах без настоящего Telegram-токена.

## Тесты

Тесты, которым требуется PostgreSQL, допускают только отдельную базу
`Kate_fitness_test` на порту `5433`. Защита тестов намеренно отказывается от
подключения к `Kate_fitness` и к порту `5432`.

```bash
docker compose -f docker-compose.db.yml up -d db_pg_test
DATABASE_URL='postgresql://USER:PASS@localhost:5433/Kate_fitness_test' \
  uv run pytest tests/
```

Pytest не загружает `.env` автоматически. Не импортируйте `sql.py` в тестах
репозитория и сервисов: создавайте `PostgresRepository` из `DATABASE_URL`.

## Изменения базы данных

Перед созданием или применением миграции сохраните резервную копию. Затем
проверьте миграцию на тестовой БД; на рабочую базу её накатывают только после
отдельного подтверждения.

```bash
DATABASE_URL='postgresql://USER:PASS@127.0.0.1:5433/Kate_fitness_test' \
  uv run alembic upgrade head
```

Миграции лежат в `alembic/versions/`. Модель существующей базы отражена в
`0001_initial_as_is.py`; не добавляйте несуществующую таблицу `payment`.

## Правила изменений

- Новое правило предметной области: сервис в `src/Kate_Fit_Notes/services/`
  и метод репозитория, а не SQL в хендлере.
- Новый шаг Telegram-сценария: UI, состояние `ScenarioState`, затем ветка
  callback-обработчика. Состояние всегда изолировано по `chat_id`.
- Новые SQL-запросы параметризуйте через `%s` и `cursor.execute(sql, params)`.
- Не коммитьте `.env`, `config.ini`, каталоги PostgreSQL, `.idea/` и дампы с
  персональными данными.
- Новые тесты размещайте только в `tests/`; корневой `test.py` — устаревший
  черновик и не используется pytest-конфигурацией.

## MCP PostgreSQL

Настройки разрешённого MCP-сервера документированы в
[`mcp/registry.yaml`](../mcp/registry.yaml). Он предназначен только для
диагностики и работы с read-only профилем. Пароли берутся из локального `.env`
и не должны появляться в командах, документации или Git.
