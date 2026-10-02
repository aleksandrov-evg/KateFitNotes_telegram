# Эксплуатация

## Сервисы Docker Compose

Compose разделён на два файла:

| Файл | Сервисы |
| --- | --- |
| `docker-compose.db.yml` | `db_pg`, `db_pg_test`, `pgadmin` |
| `docker-compose.bot.yml` | `tg_bot`, `api` |

| Сервис | Назначение | Порт хоста |
| --- | --- | --- |
| `db_pg` | рабочая PostgreSQL-база | 5432 |
| `db_pg_test` | изолированная БД для тестов | 5433 |
| `tg_bot` | Telegram-бот | — |
| `api` | FastAPI | 8000 |
| `pgadmin` | административный интерфейс PostgreSQL | 5050 |

Сеть бота: только `dokploy-network` (`external`, Traefik/Dokploy).
К БД бот ходит по `SQL_HOST` (отдельный деплой Postgres, общая Docker-сеть
не требуется).

Запуск (БД уже доступна по `SQL_HOST`):

```bash
docker network create dokploy-network 2>/dev/null || true
docker compose -f docker-compose.bot.yml up -d --build
docker compose -f docker-compose.bot.yml ps
```

API в bot-compose только `expose: 8000` (без публикации на хост) — так
удобнее Dokploy/Traefik. Локальная проверка health:

```bash
docker compose -f docker-compose.bot.yml exec api \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

Бот и API требуют reachable Postgres по `SQL_HOST`. Миграции Compose
не запускает автоматически.

## Dokploy

1. Postgres уже задеплоен отдельно и доступен с хоста/сети приложения.
2. Compose для приложения: Path `./docker-compose.bot.yml`.
3. Env: `TG_*`, `API_*`, обязательный `SQL_HOST` (IP или hostname БД),
   `SQL_PORT`, `SQL_DATABASE`.
4. Domain в UI на сервис `api`, port `8000`.
5. Не задавайте `container_name` вручную — в bot-файле его нет специально.

## Резервные копии и обновление

Перед обновлением сделайте дамп:

```bash
docker compose -f docker-compose.db.yml exec -T db_pg \
  sh -c 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' \
  > kate_fitness_YYYY-MM-DD.sql
```

Храните дамп за пределами репозитория и периодически проверяйте
восстановление. После обновления кода перезапустите только приложение:

```bash
docker compose -f docker-compose.bot.yml up -d --build
docker compose -f docker-compose.bot.yml logs --tail=100
```

Не используйте `docker compose down -v` для рабочей установки: он удаляет
Docker volumes. Для обычной остановки:

```bash
docker compose -f docker-compose.bot.yml stop
docker compose -f docker-compose.db.yml stop
```

## Безопасность

- `.env` и `config.ini` содержат секреты и не должны попадать в Git.
- `TG_ALLOWED_CHAT_IDS` ограничивает доступ к боту; пустое значение закрывает
  доступ всем.
- Не открывайте PostgreSQL, pgAdmin и API в интернет без сетевого ограничения.
- Для внешнего API используйте reverse proxy, TLS и дополнительный контроль
  доступа.
- Для Grafana создайте отдельную роль PostgreSQL с доступом только на чтение
  схемы `main`.
