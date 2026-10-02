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
TG_ACCOUNT=имя_пользователя_postgres
TG_PASS=длинный_пароль_postgres
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

Сначала поднимите базу, затем бота и API (отдельные compose-файлы):

```bash
docker compose -f docker-compose.db.yml up -d db_pg
docker network create dokploy-network 2>/dev/null || true
docker compose -f docker-compose.bot.yml up -d --build
```

В Dokploy укажите Compose Path `./docker-compose.bot.yml`, domain на сервис
`api` (порт `8000`), в env задайте `SQL_HOST=db_pg` (или hostname вашей БД).

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
