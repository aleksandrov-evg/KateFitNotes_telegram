# Kate Fit Notes

Telegram-бот фитнес-тренера для учёта клиентов, тренировок и предоплат. В
проекте также есть HTTP API с JWT-авторизацией.

## Документация и навигация

| Документ | Для чего |
| --- | --- |
| [Архитектура](docs/architecture.md) | границы слоёв, сценарии и модель данных |
| [Разработка](docs/development.md) | локальный запуск, тесты, миграции и правила изменений |
| [Эксплуатация](docs/operations.md) | запуск в Docker, резервные копии и безопасность |
| [HTTP API](docs/api.md) | аутентификация и перечень маршрутов |
| [Мониторинг Grafana](Grafana%20Dashboards/README.md) | готовые дашборды и SQL-метрики |
| [План рефакторинга](docs/refactoring/PLAN.md) | завершённые этапы и отчёты по ним |
| [Историческое ревью](docs/review.md) | исходные выводы и риски, закрытые планом рефакторинга |

Код приложения находится в `src/Kate_Fit_Notes/`, Telegram-адаптер — в
`bot.py`, миграции — в `alembic/`, тесты — в `tests/`. Локальные секреты и
данные PostgreSQL намеренно исключены из Git.

## Состав сервисов

- `tg_bot` — Telegram-бот;
- `api` — FastAPI, по умолчанию доступен на порту `8000`;
- `db_pg` — PostgreSQL с данными приложения;
- `pgadmin` — необязательная панель администрирования PostgreSQL;
- `db_pg_test` — отдельная база только для автотестов, в продакшене не нужна.

## Требования для сервера

- Docker Engine с Docker Compose v2;
- токен Telegram-бота;
- домен и reverse proxy с TLS, если API будет доступно извне;
- резервная копия существующей БД, если развёртывание выполняется поверх
  работающих данных.

## Подготовка

Клонируйте репозиторий и перейдите в его каталог:

```bash
git clone git@github.com:aleksandrov-evg/KateFitNotes_telegram.git
cd KateFitNotes_telegram
```

Создайте локальный файл конфигурации из шаблона:

```bash
cp .env.example .env
chmod 600 .env
```

Заполните в `.env` как минимум следующие значения:

```dotenv
DB_USER=имя_пользователя_postgres
DB_PASSWORD=длинный_пароль_postgres
TG_EMAIL=admin@example.com

TG_TOKEN=токен_telegram_бота
TG_ALLOWED_CHAT_IDS=123456789

API_USER=логин_api
API_PASSWORD=длинный_пароль_api
API_JWT_SECRET=случайная_длинная_секретная_строка
```

`TG_ALLOWED_CHAT_IDS` — список разрешённых Telegram `chat_id` через запятую.
Если оставить его пустым, бот не будет отвечать никому. `.env` содержит
секреты, поэтому не добавляйте его в Git и не пересылайте в чатах.

Для `API_JWT_SECRET` можно сгенерировать значение так:

```bash
openssl rand -hex 32
```

## Первый запуск

БД деплоится отдельно. В env задайте `SQL_HOST` на reachable Postgres,
затем поднимите бота и API:

```bash
docker network create dokploy-network 2>/dev/null || true
docker compose -f docker-compose.bot.yml up -d --build
```

В Dokploy укажите Compose Path `./docker-compose.bot.yml`, domain на сервис
`api` (порт `8000`), в env задайте `SQL_HOST` (IP или hostname вашей БД).

Проверьте состояние и журналы:

```bash
docker compose -f docker-compose.db.yml ps
docker compose -f docker-compose.bot.yml ps
docker compose -f docker-compose.bot.yml logs --tail=100
```

Ожидаемый ответ health-check (`{"status":"ok"}`) через domain Dokploy
или внутри контейнера:

```bash
docker compose -f docker-compose.bot.yml exec api \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

Документация API — по домену Dokploy (`/docs`) или внутри сети на
`http://api:8000/docs`. Для защищённых методов сначала JWT через
`POST /api/v1/auth/login`.

## Схема базы и миграции

Контейнеры **не применяют миграции автоматически**. Это сделано, чтобы
случайно не менять рабочую базу при обновлении. Перед первым запуском пустой
БД или перед применением новых миграций сделайте резервную копию и отдельно
подтвердите, что миграция допустима для этой БД.

После запуска `db_pg` команду можно выполнить на хосте, где установлен `uv`:

```bash
uv sync
DATABASE_URL='postgresql://USER:PASS@127.0.0.1:5432/Kate_fitness' \
  uv run alembic upgrade head
```

Замените `USER` и `PASS` на значения из `.env`. Не запускайте эту команду на
боевой базе без проверенной резервной копии и согласованной миграции.

## Обновление

Перед обновлением создайте дамп данных:

```bash
docker compose -f docker-compose.db.yml exec -T db_pg sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > kate_fitness_$(date +%F).sql
```

Затем обновите код и перезапустите только приложение (БД не трогайте):

```bash
git pull --ff-only
docker compose -f docker-compose.bot.yml up -d --build
docker compose -f docker-compose.bot.yml ps
```

Если в обновлении есть новая миграция, примените её отдельным шагом по
инструкции из предыдущего раздела.

## Безопасность и эксплуатация

- Не публикуйте наружу порты PostgreSQL `5432`, pgAdmin `5050` и API `8000`
  без ограничения доступа. В compose-файлах они проброшены на хост для
  локального администрирования.
- Для внешнего API используйте reverse proxy (например, Nginx или Caddy), TLS
  и ограничение доступа по сети или дополнительную авторизацию.
- Храните дампы БД вне каталога репозитория и регулярно проверяйте возможность
  восстановления.
- Для остановки сервисов без удаления данных используйте:

  ```bash
  docker compose -f docker-compose.bot.yml stop
  docker compose -f docker-compose.db.yml stop
  ```

  Не выполняйте `docker compose down -v` на сервере с данными: ключ `-v`
  удаляет Docker volumes. В этом проекте данные PostgreSQL также лежат в
  каталогах `pg_db/` и `pgadmin/`, которые не входят в Git.

## Локальная разработка и тесты

```bash
uv sync
docker compose -f docker-compose.db.yml up -d db_pg_test
DATABASE_URL='postgresql://USER:PASS@localhost:5433/Kate_fitness_test' \
  uv run pytest tests/
```

Тестовая БД использует отдельный порт `5433`; не направляйте `DATABASE_URL`
на рабочую БД `Kate_fitness` или порт `5432`.

## Отдельные prod и stage для сайта и API

| Настройка | Prod (текущие Compose-дефолты) | Stage |
| --- | --- | --- |
| Compose API | `docker-compose.api.yml` | `docker-compose.api.stage.yml` |
| Compose сайта | `docker-compose.ui.yml` | `docker-compose.ui.stage.yml` |
| `API_HOST_PORT` | `8000` | `8001` |
| `UI_HOST_PORT` | `8080` | `8081` |
| `UI_API_ORIGIN` | `http://katefit-api:8000` | `http://katefit-api-stage:8000` |
| `SQL_DATABASE` | `Kate_fitness` | явно задать отдельную БД, например `Kate_fitness_stage` |

Порты на хосте задаются через env; внутренние порты контейнеров фиксированы:
API `8000`, сайт `80`. Именно внутренние порты указывайте в Domain Dokploy
для сервисов `api` и `ui` соответственно, в обоих окружениях.
`UI_PORT` относится только к локальному dev-серверу, для Docker нужен `UI_HOST_PORT`.
Значения prod в таблице взяты из конфигурации репозитория; фактические настройки
запущенного Dokploy могут отличаться. На сервере порты `8001` и `8081` должны быть свободны.

В Dokploy создайте два отдельных Compose-проекта stage (API и сайт), укажите
соответствующие stage Compose Path из таблицы. Шаблон переменных —
[.env.stage.example](.env.stage.example): в API передайте `API_HOST_PORT`,
`SQL_*`, `DB_*`, `API_USER`, `API_PASSWORD`, `API_JWT_SECRET` и при необходимости
`CRM_*`; в сайт — `UI_HOST_PORT` и `UI_API_ORIGIN`.
Оба проекта подключаются к внешней `dokploy-network`. Stage API имеет отдельный
образ `katefit-api-stage` и alias `katefit-api-stage`, чтобы сайт stage обращался
к своему API. Для доменов назначьте отдельные имена stage и включите HTTPS.

Для локального запуска тех же конфигураций создайте файл `.env.stage`
из `.env.stage.example` и заполните его:

```bash
docker compose --env-file .env.stage -f docker-compose.api.stage.yml up -d --build
docker compose --env-file .env.stage -f docker-compose.ui.stage.yml up -d --build
```

БД stage и её пользователь создаются отдельно. Используйте собственные пароли
и JWT-секрет; CRM-интеграция stage по умолчанию выключена. Compose не создаёт
базу и не применяет миграции. После запуска проверьте API `/health` на порту
`8001` и сайт `/healthz` на порту `8081`, затем вход через сайт stage.
