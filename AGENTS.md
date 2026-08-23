# AGENTS.md

Инструкции для агентов, работающих с репозиторием **KateFitNotes_telegram**.

Персональный Telegram-бот фитнес-тренера (Катя). Учёт клиентов, персональных и групповых тренировок, предоплат и месячной прибыли.

Отвечать пользователю на русском. Коммиты — на русском, без упоминания Cursor.

## Стек

- Python 3.14, менеджер пакетов [uv](https://docs.astral.sh/uv/)
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) 4.7.1 (`telebot`)
- PostgreSQL 14 (`psycopg2-binary` 2.9.12, импорт `psycopg2`)
- Docker Compose (`postgres:14-alpine`, `dpage/pgadmin4`, образ бота на `uv` + Python 3.14)

Точка входа: `bot.py` → `bot.infinity_polling()`. `main.py` — заглушка PyCharm, бот её не использует.

## Карта файлов

```
bot.py                          # хендлеры, меню, callback-сценарии; состояние через SessionStore
sql.py                          # тонкие обёртки над PostgresRepository
src/Kate_Fit_Notes/settings.py        # конфиг: env, fallback config.ini
src/Kate_Fit_Notes/db.py              # пул соединений PostgreSQL
src/Kate_Fit_Notes/repository.py      # параметризованные запросы, list[dict]
src/Kate_Fit_Notes/session.py         # ScenarioState + SessionStore по chat_id
src/Kate_Fit_Notes/pipelines.py       # пустой файл, не использовать
tests/                          # автотесты (pytest), не корневой test.py
alembic/                        # миграции схемы main.* as-is
backups/kate_fitness_schema.sql # DDL Kate_fitness без данных (кластерный дамп в gitignore)
dockerfile                      # образ бота
docker-compose.yml              # pg_db :5432, pg_db_test :5433, pgadmin :5050, tg_bot
config.ini                      # не в git: TOKEN и параметры SQL
pyproject.toml                  # runtime и dev-зависимости
uv.lock                         # зафиксированные версии
.python-version                 # 3.14
.env.example                    # шаблон env без секретов
```

Не коммитить: `config.ini`, `.env`, `pg_db/`, `pg_db_test/`, `pgadmin/`, `.idea/`, секреты.

## Конфигурация

Один источник: **env**. Локальный `config.ini` — fallback, если переменной нет. Env побеждает ini. Файл ini не обязателен, если env полный. Загрузка: `src/Kate_Fit_Notes/settings.py` (`load_settings`).

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
| `TG_ACCOUNT` | пользователь PostgreSQL (`POSTGRES_USER`) | `[sql] user` |
| `TG_PASS` | пароль PostgreSQL и pgAdmin | `[sql] password` |
| `TG_EMAIL` | логин pgAdmin (`PGADMIN_DEFAULT_EMAIL`) | — |
| `SQL_DATABASE` | имя БД бота | `[sql] database` |
| `SQL_HOST` | хост БД бота | `[sql] host` |
| `SQL_PORT` | порт БД бота | `[sql] port` |
| `DATABASE_URL` | URL тестовой БД для pytest / Alembic (порт 5433, имя `*_test`) | — |

В compose у `tg_bot` задаются `SQL_HOST=db_pg`, `SQL_PORT=5432`, `SQL_DATABASE=Kate_fitness`. Postgres: `POSTGRES_DB=Kate_fitness` (прод) и `Kate_fitness_test` (тест), healthcheck `pg_isready`, бот ждёт `service_healthy`.

Тестовая БД: контейнер `pg_db_test`, порт хоста `5433`, имя `Kate_fitness_test` (`DATABASE_URL`). Pytest отказывается подключаться к `Kate_fitness` и к порту `5432`. Pytest **не** подхватывает `.env` сам — `DATABASE_URL` нужно экспортировать.

## База данных

Схема `main`. Снимок as-is в Alembic (`alembic/versions/0001_initial_as_is.py`) по дампу БД **Kate_fitness** (`backups/kate_fitness_schema.sql`). Кластерный дамп с данными в git не класть. На прод не накатывать, пока не попросили.

| Таблица            | Назначение | Ключевые поля (по дампу) |
|--------------------|------------|-----------------------------|
| `main.client`      | клиенты    | PK `phone` (id клиента), `name`, `surname`, `add_time`, `inactive` |
| `main.trains`      | типы тренировок | PK `id`, `type_train`, `group_train`, `rent_debt`, `date` |
| `main.schedule`    | записи занятий | PK `id`, UNIQUE `(date, time, client)`, `client_list bigint[]`, `studio`, `price real`, `spend`, `add_time`, `type_train_id` |
| `main.accounting`  | предоплаты | PK `id` IDENTITY, `client_id`, `summ`, `count_train`, `price_per_train`, `type_train_id`, `is_complete`, `type_action`, `comment`, `created_at`, `updated_at` |
| `main.price`       | история цен | PK `id`, `client`, `date`, `price real` |
| `main.test`        | отладка    | `dig_array bigint[]` |

Таблицы `main.payment` в проде нет. Идентификатор клиента — **телефон** (`phone`). `client_list` в БД — массив `bigint[]` (бот по-прежнему шлёт строку `{1,2,3}`).

Рабочие часы слотов: 07:00–23:00 (`work_hour` в `bot.py`). Занятые слоты на дату = `SELECT time FROM main.schedule WHERE date = ...`.

## Сценарии бота

Бот рассчитан на **одного пользователя** (whitelist — этап 12). Состояние сценария ключуется `chat_id` (`SessionStore`), не глобальный синглтон.

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
6. Подтверждение → `sql.insert_in_schedule`; при последней предоплаченной тренировке выставляется `accounting.is_complete = true`

### Групповая тренировка (`process = add_multi_train_in_schedule`)

1. Тип (`group_train = true`)
2. Мультивыбор клиентов (флаг `select` в списке)
3. Дата → время → цена → подтверждение
4. `client_list` пишется как PostgreSQL array-строка `{id1,id2,...}`; поле `client` для группы — заглушка `-1`

### Предоплата (`process = add_money_in_accounting`)

1. Клиент → тип тренировки
2. Текст: `<сумма> <количество>`, например `1000 10`
3. Подтверждение → `sql.insert_in_accounting`

## Состояние: `SessionStore` по `chat_id`

Один объект `ScenarioState` на чат (`src/Kate_Fit_Notes/session.py`). Запись и оплата — поля того же объекта, разные `process`. Модульный `sessions` в `bot.py`; хендлеры берут `sessions.get(message.chat.id)`.

Поля процесса: `process` (pipeline), `operation` (шаг). Callback'и смотрят на пару `(process, operation)` и на `call.data`.

`call.data` часто — **индекс в текущем списке** (`list_client`, `list_train`, `list_time`), а не id из БД. Для мультивыбора клиента `callback_data` = `phone`. Не менять формат callback без проверки всех `match`/`if` в `callback_inline`.

Сброс: `sessions.clear(chat_id)` при `/start` и «В главное меню»; при входе в персональную/групповую запись и «Добавить оплату» — `clear(chat_id, process=...)`. Сброс затрагивает только этот чат.

## SQL-слой (`sql.py` / `repository.py`)

- Репозиторий: `src/Kate_Fit_Notes/repository.py` (`PostgresRepository`). Соединения — пул в `src/Kate_Fit_Notes/db.py` (`with` + `putconn` в `finally`).
- `sql.py` — тонкие обёртки с прежними именами функций; при импорте вызывает `load_settings()`.
- Выборки возвращают `list[dict]`; пустой список — нет строк. Число строк — `len(rows)`, не `result[1]` / `result[2]`. `select_time_at_data` — список времён. INSERT/UPDATE — `None`.
- Запросы с плейсхолдерами `%s` / `cursor.execute(sql, params)`. Логируется только `statusmessage`, не полный SQL с телефонами.
- Тесты репозитория импортируют `repository` / `db` и собирают его из `DATABASE_URL`. Не импортировать `bot.py` / `sql.py`.

Типичные функции:

- клиенты: `search_client`, `insert_client_data`, `show_all_clients`, `select_last_client`
- тренировки: `list_all_train(group: bool)`
- расписание: `select_time_at_data`, `insert_in_schedule`
- предоплата: `insert_in_accounting`, `get_active_prepaid_for_client`, `get_count_prepaid_train`, `get_last_price_for_train`
- отчёт: `get_incom_all_month_balance`

## Как запускать

Локально (env `TG_TOKEN` / `TG_ACCOUNT` / `TG_PASS` / `SQL_*` или fallback `config.ini`):

```bash
uv sync
uv run python bot.py
```

Инфраструктура:

```bash
docker compose up -d db_pg pgadmin
docker compose build tg_bot
# или: docker build -t telegram_bot:latest .
docker compose up -d tg_bot
```

pgAdmin: `http://localhost:5050`. Postgres: `localhost:5432` (прод-данные), `localhost:5433` (тест).

Тесты (нужны `DATABASE_URL` на `localhost:5433` / `Kate_fitness_test`, не прод):

```bash
uv sync
docker compose up -d db_pg_test
# DATABASE_URL как в .env.example
uv run pytest tests/
```

Без `DATABASE_URL` DB-тесты скипаются. Живой Telegram-токен для `pytest tests/` не нужен. Не импортировать `bot.py` / `sql.py` в тестах: они вызывают `load_settings()` при импорте. Тесты репозитория: `PostgresRepository.from_dsn(DATABASE_URL)`.

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
- Не делать полноценный multi-user продукт сверх ключа `chat_id` (whitelist — этап 12).
- Не менять смысл `client` = телефон и формат `client_list` `{1,2,3}` без миграции данных.
- Не писать новые фичи в `main.py` или пустой `pipelines.py`.
- Не запускать `git push` и не менять git config без просьбы.
- Не коммитить изменения `.idea/`, если пользователь не просил.

## Типичные точки расширения

| Задача | Куда смотреть |
|--------|----------------|
| Новый пункт меню | `start()`, ветка в `get_text_messages()` |
| Новый шаг сценария | функции `show_*` + ветка в `callback_inline` |
| Новая выборка/запись | метод в `repository.py`, обёртка в `sql.py`, вызов из `bot.py` |
| Поля состояния сценария | `ScenarioState` / `SessionStore` в `session.py` |
