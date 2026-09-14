# Kate Fit Notes

Telegram-бот фитнес-тренера для учёта клиентов, тренировок и предоплат. В
проекте также есть HTTP API с JWT-авторизацией.

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

Соберите образы и запустите PostgreSQL, бота и API:

```bash
docker compose up -d --build db_pg tg_bot api
```

Проверьте состояние и журналы:

```bash
docker compose ps
docker compose logs --tail=100 tg_bot api
curl http://127.0.0.1:8000/health
```

Ожидаемый ответ health-check:

```json
{"status":"ok"}
```

Документация API доступна по адресу `http://SERVER:8000/docs`. Для работы с
защищёнными методами сначала получите JWT через `POST /api/v1/auth/login`.

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
docker compose exec -T db_pg sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > kate_fitness_$(date +%F).sql
```

Затем обновите код и перезапустите сервисы:

```bash
git pull --ff-only
docker compose up -d --build tg_bot api
docker compose ps
curl http://127.0.0.1:8000/health
```

Если в обновлении есть новая миграция, примените её отдельным шагом по
инструкции из предыдущего раздела.

## Безопасность и эксплуатация

- Не публикуйте наружу порты PostgreSQL `5432`, pgAdmin `5050` и API `8000`
  без ограничения доступа. В текущем compose-файле они проброшены на хост для
  локального администрирования.
- Для внешнего API используйте reverse proxy (например, Nginx или Caddy), TLS
  и ограничение доступа по сети или дополнительную авторизацию.
- Храните дампы БД вне каталога репозитория и регулярно проверяйте возможность
  восстановления.
- Для остановки сервисов без удаления данных используйте:

  ```bash
  docker compose stop
  ```

  Не выполняйте `docker compose down -v` на сервере с данными: ключ `-v`
  удаляет Docker volumes. В этом проекте данные PostgreSQL также лежат в
  каталогах `pg_db/` и `pgadmin/`, которые не входят в Git.

## Локальная разработка и тесты

```bash
uv sync
docker compose up -d db_pg_test
DATABASE_URL='postgresql://USER:PASS@localhost:5433/Kate_fitness_test' \
  uv run pytest tests/
```

Тестовая БД использует отдельный порт `5433`; не направляйте `DATABASE_URL`
на рабочую БД `Kate_fitness` или порт `5432`.
