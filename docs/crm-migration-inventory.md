# Инвентаризация Kate_fitness для моста в CRM

Дата: 2026-10-02.

## Статус живой БД

На момент инвентаризации локальный Postgres/`docker compose` недоступны
(`Connection refused`, Docker daemon не запущен). Counts и дубликаты phone
нужно снять на живой `Kate_fitness` перед one-shot импортом:

```sql
SELECT 'client' AS t, COUNT(*) FROM main.client
UNION ALL SELECT 'schedule', COUNT(*) FROM main.schedule
UNION ALL SELECT 'accounting', COUNT(*) FROM main.accounting
UNION ALL SELECT 'trains', COUNT(*) FROM main.trains
UNION ALL SELECT 'schedule_participant', COUNT(*) FROM main.schedule_participant
UNION ALL SELECT 'price', COUNT(*) FROM main.price;

SELECT COUNT(*) AS duplicate_phones FROM (
  SELECT phone FROM main.client GROUP BY phone HAVING COUNT(*) > 1
) d;

SELECT
  COUNT(*) FILTER (WHERE studio IS NOT NULL AND btrim(studio) <> '') AS studio_nonempty,
  COUNT(*) AS schedule_total
FROM main.schedule;

SELECT location, COUNT(*) FROM main.trains GROUP BY location ORDER BY 1;
```

## Выводы по схеме / seed (без живых данных)

| Сущность | Источник | Вывод |
| --- | --- | --- |
| `main.trains` | `tests/seed.py` (дамп 2026-08-22) | 17 типов; `location` ∈ {`ter_fit`, `home`}; только `[дом] Реформер` → `home` |
| `main.schedule.studio` | DDL + `insert_in_schedule` | Колонка legacy; runtime INSERT **не пишет** `studio` — в CRM не маппить |
| Дифференциация места | `trains.location` | Канон для фильтров CRM |
| Дифференциация формата | `trains.group_train` / `schedule.is_group` | Перс vs группа |
| Клиент | UNIQUE `phone` (10 цифр) | Ключ сопоставления mirror Person |
| История | типы с 2023-04 | ≥ ~3 лет данных ожидаемо на проде |

## Правило SoT для CRM

PostgreSQL `Kate_fitness` — единственный источник правды линии личных ПТ.
Twenty app `katfit-personal` — зеркало + write-through через HTTP API.
