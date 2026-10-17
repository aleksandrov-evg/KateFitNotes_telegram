### Результат проверки — этап 11

- [x] Автотесты написаны (секция тестировщика закрыта)
- [x] Автотесты зелёные (`pytest` без ошибок)
- [x] Код-ревью проведено, саммари заполнено
- [x] Вердикт MERGE — этап можно закрывать

**Команда:** `pytest tests/`
**Результат прогона:** 148 passed / 0 failed (с `DATABASE_URL` на `*:5433/Kate_fitness_test`); без URL — 108 passed / 40 skipped
**Вердикт ревьювера:** MERGE
**Саммари:** Alembic `0002_site_model` даёт `client.id` (телефон UNIQUE), `schedule_participant`, `schedule.accounting_id`, UNIQUE `(date, time)`, FK/CHECK. Списание пакета только по `accounting_id`. Группа без `client=-1`. Callback клиента — surrogate id. `spend` не выдумывали. Прод не накатывали. Блокеров нет.
**Дата:** 23.08.2026
