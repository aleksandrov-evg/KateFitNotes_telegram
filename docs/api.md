# HTTP API

API создаётся фабрикой `create_app(settings, repository)` и доступен через
Swagger UI по `/docs`. Проверить доступность можно без авторизации:

```bash
curl http://127.0.0.1:8000/health
```

Все маршруты `/api/v1/*`, кроме входа, требуют JWT. Получите токен запросом
`POST /api/v1/auth/login` с учётными данными `API_USER` и `API_PASSWORD`,
затем передавайте его в заголовке `Authorization: Bearer <token>`.

| Метод | Маршрут | Назначение |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | получить JWT |
| `GET` | `/api/v1/clients` | список клиентов с поиском и пагинацией |
| `POST` | `/api/v1/clients` | создать клиента |
| `GET` | `/api/v1/clients/{client_id}` | получить клиента |
| `GET` | `/api/v1/train-types?group=` | типы; `group` опционален (`true`/`false`/пусто=все); в ответе есть `location` |
| `GET` | `/api/v1/slots?date=YYYY-MM-DD` | свободные слоты даты |
| `GET` | `/api/v1/bookings?from&to&client_id&updated_since` | список занятий для CRM sync |
| `POST` | `/api/v1/bookings/personal` | создать персональную запись |
| `POST` | `/api/v1/bookings/group` | создать групповую запись |
| `GET` | `/api/v1/prepaid?client_id&active&updated_since` | список пакетов (с `used_count` / `remaining`) |
| `POST` | `/api/v1/prepaid` | добавить пакет предоплаты |
| `GET` | `/api/v1/reports/monthly` | отчёт по месяцам |

Для отчёта за один месяц передайте оба параметра: `year` и `month`. Форматы
тел запросов и ответов определены в `src/Kate_Fit_Notes/api/schemas.py`; они
же являются точным контрактом API.

Курсор sync: `updated_since` для bookings опирается на `schedule.add_time`,
для prepaid — на `accounting.updated_at`. Идемпотентный ключ зеркала CRM —
`id` занятия / пакета.
