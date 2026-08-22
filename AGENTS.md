# AGENTS.md

Инструкции для агентов, работающих с репозиторием **KateFitNotes_telegram**.

Персональный Telegram-бот фитнес-тренера (Катя). Учёт клиентов, персональных и групповых тренировок, предоплат и месячной прибыли.

Отвечать пользователю на русском. Коммиты — на русском, без упоминания Cursor.

## Стек

- Python 3.11
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) 4.7.1 (`telebot`)
- PostgreSQL 14 (`psycopg2` 2.9.5)
- Docker Compose (`postgres:14-alpine`, `dpage/pgadmin4`, образ бота)

Точка входа: `bot.py` → `bot.infinity_polling()`. `main.py` — заглушка PyCharm, бот её не использует.

## Карта файлов

```
bot.py                          # хендлеры, меню, callback-сценарии, глобальное состояние
sql.py                          # все SQL-запросы к PostgreSQL
src/Kate_Fit_Notes/process_class.py   # класс CurrentData (состояние сценария оплаты)
src/Kate_Fit_Notes/pipelines.py       # пустой файл, не использовать
tests/                          # автотесты (pytest), не корневой test.py
alembic/                        # миграции схемы main.* as-is
backups/kate_fitness_schema.sql # DDL Kate_fitness без данных (кластерный дамп в gitignore)
dockerfile                      # образ бота
docker-compose.yml              # pg_db :5432, pg_db_test :5433, pgadmin :5050, tg_bot
config.ini                      # не в git: TOKEN и параметры SQL
requirements.txt                # runtime
requirements-dev.txt            # pytest, alembic
.env.example                    # шаблон env без секретов
```

Не коммитить: `config.ini`, `.env`, `pg_db/`, `pg_db_test/`, `pgadmin/`, секреты.

## Конфигурация

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

Если `host` пустой, `sql.py` пытается взять IP контейнера `pg_db` через `docker inspect`.

Переменные окружения (`.env` / compose):

| Переменная     | Назначение                                      |
|----------------|-------------------------------------------------|
| `TG_ACCOUNT`   | пользователь PostgreSQL (`POSTGRES_USER`)       |
| `TG_PASS`      | пароль PostgreSQL и pgAdmin                     |
| `TG_EMAIL`     | логин pgAdmin (`PGADMIN_DEFAULT_EMAIL`)         |
| `DATABASE_URL` | URL тестовой БД для pytest / Alembic (порт 5433, имя `*_test`) |

Подключение к БД в `sql.py` берёт `user`/`password` из `os.environ['TG_ACCOUNT']` / `os.environ['TG_PASS']`, а `database`/`host`/`port` — из `config.ini`.

Тестовая БД: контейнер `pg_db_test`, порт хоста `5433`, имя `Kate_fitness_test` (`DATABASE_URL`). Pytest отказывается подключаться к `Kate_fitness` и к порту `5432`.

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

Бот рассчитан на **одного пользователя**. Состояние глобальное, без привязки к `chat_id`.

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

### Предоплата (`current_data_new.process = add_money_in_accounting`)

1. Клиент → тип тренировки
2. Текст: `<сумма> <количество>`, например `1000 10`
3. Подтверждение → `sql.insert_in_accounting`

## Состояние: два контура

Не объединять без явной задачи. Сейчас живут параллельно:

1. **`current_data`** — `dict` + `current_data_clear()`. Сценарии расписания (персональные/групповые тренировки).
2. **`current_data_new`** — экземпляр `CurrentData`. Сценарий «Добавить оплату».

Поля процесса: `process` (pipeline), `operation` (шаг). Callback'и смотрят на пару `(process, operation)` и на `call.data`.

`call.data` часто — **индекс в текущем списке** (`list_client`, `list_train`, `list_time`), а не id из БД. Для мультивыбора клиента `callback_data` = `phone`. Не менять формат callback без проверки всех `match`/`if` в `callback_inline`.

Сброс: `current_data_clear()` при `/start` и при входе в сценарий тренировки. Для оплаты процесс задаётся так: `current_data_new.process = "add_money_in_accounting"`.

## SQL-слой (`sql.py`)

- `execute_query(text)` открывает соединение, `autocommit=True`, печатает лог.
- Для `SELECT` возвращает список вида `['SELECT', '<n>', list[dict]]`. Код бота читает `result[1]` (число строк) и `result[2]` (строки). Для `INSERT`/`UPDATE` возвращается `None` — это учитывают хендлеры.
- Запросы собираются f-строками с подстановкой значений. **Не добавлять пользовательский ввод в SQL без санитизации**; новые запросы лучше писать с плейсхолдерами `%s` / `cursor.execute(sql, params)`.
- Не переписывать все существующие запросы на параметризацию в рамках мелкой задачи.

Типичные функции:

- клиенты: `search_client`, `insert_client_data`, `show_all_clients`, `select_last_client`
- тренировки: `list_all_train(group: bool)`
- расписание: `select_time_at_data`, `insert_in_schedule`
- предоплата: `insert_in_accounting`, `get_active_prepaid_for_client`, `get_count_prepaid_train`, `get_last_price_for_train`
- отчёт: `get_incom_all_month_balance`

## Как запускать

Локально (нужны `config.ini` и env `TG_ACCOUNT`/`TG_PASS`):

```bash
python3 bot.py
```

Инфраструктура:

```bash
docker compose up -d db_pg pgadmin
# образ бота: docker build -t telegram_bot:latest .
docker compose up -d tg_bot
```

pgAdmin: `http://localhost:5050`. Postgres: `localhost:5432` (прод-данные), `localhost:5433` (тест).

В `dockerfile` команда `CMD ["python3","-m", "bot.py"]` некорректна для запуска модуля; рабочий вариант — `python3 bot.py`. Не «чинить» это попутно, если задача не про Docker.

Тесты (нужны `DATABASE_URL` на `localhost:5433` / `Kate_fitness_test`, не прод):

```bash
pip install -r requirements-dev.txt
docker compose up -d db_pg_test
# DATABASE_URL как в .env.example
pytest tests/
```

Без `DATABASE_URL` DB-тесты скипаются. Не импортировать `bot.py` в тестах: он читает токен из `config.ini`.

## Соглашения по коду

- UI и сообщения бота — на русском.
- Новые хендлеры: сначала клавиатура/inline, затем запись в состояние, затем переход к следующей функции-шагу. Не плодить FSM-библиотеку, пока явно не попросили.
- Клавиатуры: `ReplyKeyboardMarkup` для главного меню, `InlineKeyboardMarkup` для выбора из списков.
- Телефон: 11 цифр с `7`/`8` или 12 символов `+7…`; в БД кладётся 10 цифр без кода страны.
- Цены и количества — целые; ввод проверять `.isdigit()`.
- После успешной/отменённой записи возвращать в `start()`.
- `try/except` вокруг insert уже есть и глотает любые ошибки — при правках логировать исключение, не оставлять голый `except:`.
- Не добавлять README, линтеры, рефакторинг `current_data` vs `CurrentData`, параметризацию всего SQL, если это не часть задачи.
- `keyboa` в runtime не нужен.

## Чего не делать

- Не коммитить токен бота, пароли, дампы `pg_db/`.
- Не вводить multi-user state, пока бот однопользовательский, без явного запроса.
- Не менять смысл `client` = телефон и формат `client_list` `{1,2,3}` без миграции данных.
- Не писать новые фичи в `main.py` или пустой `pipelines.py`.
- Не запускать `git push` и не менять git config без просьбы.
- Не коммитить изменения `.idea/`, если пользователь не просил.

## Типичные точки расширения

| Задача | Куда смотреть |
|--------|----------------|
| Новый пункт меню | `start()`, ветка в `get_text_messages()` |
| Новый шаг сценария | функции `show_*` + ветка в `callback_inline` |
| Новая выборка/запись | функция в `sql.py`, вызов из `bot.py` |
| Поля состояния оплаты | `CurrentData` в `process_class.py` |
| Поля состояния расписания | словарь в `current_data_clear()` |
