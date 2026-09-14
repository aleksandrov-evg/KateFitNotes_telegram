# AGENTS.md

Инструкции для агентов, работающих с репозиторием **KateFitNotes_telegram**.

Персональный Telegram-бот фитнес-тренера (Катя). Учёт клиентов, персональных и групповых тренировок, предоплат и месячной прибыли.

Отвечать пользователю на русском. Коммиты — на русском, без упоминания Cursor.

## Стек

- Python 3.14, менеджер пакетов [uv](https://docs.astral.sh/uv/)
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) 4.7.1 (`telebot`)
- FastAPI 0.141.1 + uvicorn 0.52.4 + PyJWT 2.13.0 (HTTP API)
- PostgreSQL 14 (`psycopg2-binary` 2.9.12, импорт `psycopg2`)
- Docker Compose (`postgres:14-alpine`, `dpage/pgadmin4`, образ бота на `uv` + Python 3.14)

Точка входа бота: `uv run python bot.py` → `create_bot(...).bot.infinity_polling()` под `if __name__ == "__main__"`. `import bot` не стартует polling и не вызывает `load_settings()`. `main.py` — заглушка PyCharm, бот её не использует.

Точка входа API: `uv run uvicorn src.Kate_Fit_Notes.api.app:app_from_env --factory`. `create_app(settings, repository)` не требует живой Telegram. Сайт не начинать.

## Карта файлов

```
bot.py                          # тонкий адаптер: create_bot, хендлеры без SQL, whitelist chat_id
sql.py                          # тонкие обёртки над PostgresRepository
src/Kate_Fit_Notes/api/               # FastAPI: create_app, JWT, роуты поверх сервисов
src/Kate_Fit_Notes/settings.py        # конфиг: env, fallback config.ini
src/Kate_Fit_Notes/db.py              # пул соединений PostgreSQL
src/Kate_Fit_Notes/repository.py      # параметризованные запросы, list[dict]
src/Kate_Fit_Notes/session.py         # ScenarioState + SessionStore по chat_id
src/Kate_Fit_Notes/bot_ui.py          # клавиатуры и тексты (markup без send_message)
src/Kate_Fit_Notes/pipelines.py       # пустой файл, не использовать
tests/                          # автотесты (pytest), не корневой test.py
alembic/                        # миграции схемы main.* as-is
backups/kate_fitness_schema.sql # DDL Kate_fitness без данных (кластерный дамп в gitignore)
dockerfile                      # образ бота
docker-compose.yml              # pg_db :5432, pg_db_test :5433, pgadmin :5050, tg_bot, api :8000
config.ini                      # не в git: TOKEN и параметры SQL
pyproject.toml                  # runtime и dev-зависимости
uv.lock                         # зафиксированные версии
.python-version                 # 3.14
.env.example                    # шаблон env без секретов
```

Не коммитить: `config.ini`, `.env`, `pg_db/`, `pg_db_test/`, `pgadmin/`, `.idea/`, секреты.

## Конфигурация

Один источник: **env**. Локальный `config.ini` — fallback, если переменной нет. Env побеждает ini. Файл ini не обязателен, если env полный. Загрузка: `src/Kate_Fit_Notes/settings.py` (`load_settings`).

## MCP для агентов

Реестр доступных MCP-серверов хранится в `mcp/registry.yaml`; готовые фрагменты конфигурации Codex — в `mcp/`. MCP PostgreSQL запускается только из корня этого репозитория через `mcp/run_postgres_mcp.sh`. Перед использованием MCP агент сверяет назначение и ограничения в реестре. В Git попадают только несекретные параметры подключения и имена переменных; значения ключей, токенов и паролей остаются в локальном `.env` или системной связке ключей.

`config.ini` (локальный, в `.gitignore`):

```ini
[main]
TOKEN=<telegram_bot_token>

[sql]
database=Kate_fitness
user=root
password=root
host=db_pg
port=5432
```

`SQL_HOST` обязателен (env или `[sql] host`). Пустой host — ошибка конфига, без `docker inspect`.

Переменные окружения (`.env` / compose):

| Переменная | Назначение | Fallback ini |
|------------|------------|--------------|
| `TG_TOKEN` | токен Telegram-бота | `[main] TOKEN` |
| `TG_ALLOWED_CHAT_IDS` | whitelist `chat_id` через запятую; пусто — никто | — |
| `API_USER` | логин HTTP API (JWT) | — |
| `API_PASSWORD` | пароль HTTP API | — |
| `API_JWT_SECRET` | секрет подписи JWT | — |
| `TG_ACCOUNT` | пользователь PostgreSQL (`POSTGRES_USER`) | `[sql] user` |
| `TG_PASS` | пароль PostgreSQL и pgAdmin | `[sql] password` |
| `TG_EMAIL` | логин pgAdmin (`PGADMIN_DEFAULT_EMAIL`) | — |
| `SQL_DATABASE` | имя БД бота | `[sql] database` |
| `SQL_HOST` | хост БД бота | `[sql] host` |
| `SQL_PORT` | порт БД бота | `[sql] port` |
| `DATABASE_URL` | URL тестовой БД для pytest / Alembic (порт 5433, имя `*_test`) | — |

В compose у `tg_bot` и `api` задаются `SQL_HOST=db_pg`, `SQL_PORT=5432`, `SQL_DATABASE=Kate_fitness`. Postgres: `POSTGRES_DB=Kate_fitness` (прод) и `Kate_fitness_test` (тест), healthcheck `pg_isready`, бот и API ждут `service_healthy`. API слушает `:8000`. Пустой `TG_ALLOWED_CHAT_IDS` — бот никому не отвечает.

Тестовая БД: контейнер `pg_db_test`, порт хоста `5433`, имя `Kate_fitness_test` (`DATABASE_URL`). Pytest отказывается подключаться к `Kate_fitness` и к порту `5432`. Pytest **не** подхватывает `.env` сам — `DATABASE_URL` нужно экспортировать.

## База данных

Схема `main`. Снимок as-is в Alembic (`alembic/versions/0001_initial_as_is.py`) по дампу БД **Kate_fitness** (`backups/kate_fitness_schema.sql`). Кластерный дамп с данными в git не класть. На прод не накатывать, пока не попросили.

| Таблица | Назначение | Ключевые поля |
|--------------------|------------|-----------------------------|
| `main.client` | клиенты | PK `id`, UNIQUE `phone`, `name`, `surname`, `add_time`, `inactive` |
| `main.trains` | типы тренировок | PK `id`, `type_train`, `group_train`, `rent_debt`, `date` |
| `main.schedule` | записи занятий | PK `id`, UNIQUE `(date, time)`, `client_id` (NULL у группы), `accounting_id`, `studio`, `price real`, `spend`, `add_time`, `type_train_id` |
| `main.schedule_participant` | участники занятия | PK `(schedule_id, client_id)`, FK на `schedule` и `client` |
| `main.accounting` | предоплаты | PK `id` IDENTITY, `client_id` → `client.id`, `summ`, `count_train`, `price_per_train`, `type_train_id`, `is_complete`, `type_action`, `comment`, `created_at`, `updated_at` |
| `main.price` | история цен | PK `id`, `client_id` → `client.id`, `date`, `price real` |
| `main.test` | отладка | `dig_array bigint[]` |

Таблицы `main.payment` в проде нет. Идентификатор клиента — surrogate `id`; телефон — уникальное поле. Участники группы — `schedule_participant`, не `client_list` и не `client = -1`. Списание пакета — по `schedule.accounting_id`. Схема as-is в `0001`, модель сайта — `0002_site_model`. На прод не накатывать, пока не попросили.

Рабочие часы слотов: 07:00–23:00 (`domain.work_slots`). Занятые слоты на дату = `SELECT time FROM main.schedule WHERE date = ...`.

## Сценарии бота

Бот рассчитан на **одного пользователя**: whitelist `TG_ALLOWED_CHAT_IDS`. Чат не из списка получает «Нет доступа», сервисы не вызываются. Состояние сценария ключуется `chat_id` (`SessionStore`), не глобальный синглтон.

Главное меню (`/start` и кнопка «🔙 В главное меню»):

- `➕ Новый клиент` — ждать контакт Telegram, распарсить телефон (`+7` / `7` / `8`), записать в `main.client`
- `Добавить оплату` — предоплата пакета
- `💰 Отчет по тренировкам` — помесячный `income = sum(price) - sum(rent_debt)` из `main.schedule`
- `➕🤸 Добавить перс. тренировку`
- `➕👯 Добавить груп. тренировку`

Закомментированы: расписание, настройка тренировок.

### Персональная тренировка (`process = add_single_train_in_schedule`)

1. Клиент (недавно ходившие; кнопка «Показать всех»)
2. Тип тренировки (`main.trains` где `group_train = false`)
3. Дата (неделя, `<< неделя` / `Эта неделя` / `неделя >>`)
4. Свободное время
5. Цена (если есть незакрытая предоплата — подсказка / блок при >1 авансе)
6. Подтверждение → `BookingService.book_personal`; при последней предоплаченной тренировке выставляется `accounting.is_complete = true`

### Групповая тренировка (`process = add_multi_train_in_schedule`)

1. Тип (`group_train = true`)
2. Мультивыбор клиентов (флаг `select` в списке)
3. Дата → время → цена → подтверждение
4. Участники пишутся в `schedule_participant`; у группы `schedule.client_id` = NULL, `is_group = true`

### Предоплата (`process = add_money_in_accounting`)

1. Клиент → тип тренировки
2. Текст: `<сумма> <количество>`, например `1000 10`
3. Подтверждение → `PrepaidService.add_package`

## Состояние: `SessionStore` по `chat_id`

Один объект `ScenarioState` на чат (`src/Kate_Fit_Notes/session.py`). Запись и оплата — поля того же объекта, разные `process`. `create_bot` держит `SessionStore`; хендлеры берут `sessions.get(message.chat.id)`.

Поля процесса: `process` (pipeline), `operation` (шаг). Callback'и смотрят на пару `(process, operation)` и на `call.data`.

`callback_data` — id сущности: `client.id`, `trains.id`, ISO-дата, время `HH:MM`. Служебные кнопки (`show_all_client_single`, `approve_add`, `prev_week`, …) — строки. Если id нет в текущем `list_*` (устаревшая кнопка) — выход без записи, без IndexError.

Сброс: `sessions.clear(chat_id)` при `/start` и «В главное меню»; при входе в персональную/групповую запись и «Добавить оплату» — `clear(chat_id, process=...)`. Сброс затрагивает только этот чат.

## SQL-слой (`sql.py` / `repository.py`)

- Репозиторий: `src/Kate_Fit_Notes/repository.py` (`PostgresRepository`). Соединения — пул в `src/Kate_Fit_Notes/db.py` (`with` + `putconn` в `finally`).
- `sql.py` — тонкие обёртки с прежними именами функций; при импорте вызывает `load_settings()`.
- Выборки возвращают `list[dict]`; пустой список — нет строк. Число строк — `len(rows)`, не `result[1]` / `result[2]`. `select_time_at_data` — список времён. `insert_client_data` — `RETURNING id`. Остальные INSERT/UPDATE — `None`.
- Запросы с плейсхолдерами `%s` / `cursor.execute(sql, params)`. Логируется только `statusmessage`, не полный SQL с телефонами.
- Тесты репозитория и сервисов импортируют `repository` / `db` и собирают его из `DATABASE_URL`. Не импортировать `sql.py`. `bot.py` можно импортировать в `tests/test_bot.py` (`create_bot` с фейковым репо).

Типичные функции:

- клиенты: `search_client`, `insert_client_data`, `get_client`, `list_clients`, `show_all_clients`, `select_last_client`
- тренировки: `list_all_train(group: bool)`
- расписание: `select_time_at_data`, `insert_in_schedule`
- предоплата: `insert_in_accounting`, `get_active_prepaid_for_client`, `get_count_prepaid_train`, `get_last_price_for_train`
- отчёт: `get_incom_all_month_balance`

## Как запускать

Локально (env `TG_TOKEN` / `TG_ACCOUNT` / `TG_PASS` / `SQL_*` или fallback `config.ini`):

```bash
uv sync
uv run python bot.py
# HTTP API (нужны API_USER / API_PASSWORD / API_JWT_SECRET):
uv run uvicorn src.Kate_Fit_Notes.api.app:app_from_env --factory --host 127.0.0.1 --port 8000
```

Инфраструктура:

```bash
docker compose up -d db_pg pgadmin
docker compose build tg_bot
# или: docker build -t telegram_bot:latest .
docker compose up -d tg_bot
docker compose up -d api
```

pgAdmin: `http://localhost:5050`. Postgres: `localhost:5432` (прод-данные), `localhost:5433` (тест).

Тесты (нужны `DATABASE_URL` на `localhost:5433` / `Kate_fitness_test`, не прод):

```bash
uv sync
docker compose up -d db_pg_test
# DATABASE_URL как в .env.example
uv run pytest tests/
```

Без `DATABASE_URL` DB-тесты скипаются. Живой Telegram-токен для `pytest tests/` не нужен: `import bot` не вызывает `load_settings()`. Остальные тесты не импортируют `sql.py`. Тесты репозитория: `PostgresRepository.from_dsn(DATABASE_URL)`. Тесты адаптера: `create_bot(settings, fake_repo)` в `tests/test_bot.py`. Тесты API: `create_app(settings, fake_repo)` в `tests/test_api.py` (`TestClient`, без polling).

## Соглашения по коду

- UI и сообщения бота — на русском.
- Новые хендлеры: сначала клавиатура/inline, затем запись в состояние, затем переход к следующей функции-шагу. Не плодить FSM-библиотеку, пока явно не попросили.
- Клавиатуры: `ReplyKeyboardMarkup` для главного меню, `InlineKeyboardMarkup` для выбора из списков.
- Телефон: 11 цифр с `7`/`8` или 12 символов `+7…`; в БД кладётся 10 цифр без кода страны.
- Цены и количества — целые; ввод проверять `.isdigit()`.
- После успешной/отменённой записи возвращать в `start()`.
- `try/except` вокруг insert уже есть и глотает любые ошибки — при правках логировать исключение, не оставлять голый `except:`.
- Не добавлять README, линтеры, параметризацию всего SQL, если это не часть задачи. Не разводить снова два контура состояния.
- `keyboa` в runtime не нужен.

## Чего не делать

- Не коммитить токен бота, пароли, дампы `pg_db/`.
- Не делать полноценный multi-user продукт сверх ключа `chat_id` и whitelist.
- Не откатывать PK клиента на телефон и не возвращать `client_list` / `client = -1` без новой миграции.
- Не писать новые фичи в `main.py` или пустой `pipelines.py`.
- Не запускать `git push` и не менять git config без просьбы.
- Не коммитить изменения `.idea/`, если пользователь не просил.

## Типичные точки расширения

| Задача | Куда смотреть |
|--------|----------------|
| Новый пункт меню | `BotApp.start` / `get_text_messages`, тексты в `bot_ui.py` |
| Новый шаг сценария | методы `show_*` + ветка в `callback_inline` |
| Новая выборка/запись | метод в `repository.py` и сервисе; хендлер только вызывает сервис |
| Поля состояния сценария | `ScenarioState` / `SessionStore` в `session.py` |
| HTTP API | `src/Kate_Fit_Notes/api/`, `create_app`; не писать SQL в роутах |
