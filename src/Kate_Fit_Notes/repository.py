"""Репозиторий PostgreSQL: параметризованный SQL, list[dict]. Без load_settings при импорте."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Iterable, Protocol

from psycopg2.extras import RealDictCursor

from src.Kate_Fit_Notes.db import ConnectionPool
from src.Kate_Fit_Notes.domain import ACCOUNTING_NOW_SQL
from src.Kate_Fit_Notes.settings import Settings

logger = logging.getLogger(__name__)


class KateFitRepository(Protocol):
    def search_client(self, phone_number: Any) -> list[dict]: ...

    def insert_client_data(
        self, phone_number: Any, name: str = "None", surname: str = "None"
    ) -> int | None: ...

    def show_all_clients(self) -> list[dict]: ...

    def select_last_client(self, number_client: int = 0) -> list[dict]: ...

    def list_all_train(self, group: bool) -> list[dict]: ...

    def get_train(self, train_id: Any) -> dict | None: ...

    def select_time_at_data(self, date: Any) -> list: ...

    def get_schedule_at(self, date: Any, time: Any) -> dict | None: ...

    def get_schedule_participants(self, schedule_id: Any) -> list[int]: ...

    def insert_in_schedule(
        self,
        date: Any,
        client_id: Any,
        participant_ids: Any,
        time: Any,
        rent_debt: Any,
        type_train: Any,
        is_group: Any,
        train_price: Any,
        type_train_id: Any,
        set_is_complete_true: Any = False,
        accounting_id: Any = None,
    ) -> None: ...

    def insert_in_accounting(
        self,
        client_id: Any,
        summ: Any,
        count_train: Any,
        price_per_train: Any,
        type_train_id: Any,
    ) -> None: ...

    def get_active_prepaid_for_client(
        self, client_id: Any, type_train_id: Any
    ) -> list[dict]: ...

    def get_count_prepaid_train(
        self, client_id: Any, type_train_id: Any
    ) -> list[dict]: ...

    def get_last_price_for_train(
        self, client_id: Any, type_train_id: Any
    ) -> list[dict]: ...

    def get_incom_all_month_balance(self) -> list[dict]: ...


def _as_id_list(raw: Iterable | None) -> list[int]:
    if not raw:
        return []
    return [int(item) for item in raw]


class PostgresRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    @classmethod
    def from_settings(cls, settings: Settings) -> PostgresRepository:
        return cls(ConnectionPool.from_settings(settings))

    @classmethod
    def from_dsn(cls, dsn: str) -> PostgresRepository:
        return cls(ConnectionPool.from_dsn(dsn))

    @property
    def pool(self) -> ConnectionPool:
        return self._pool

    def close(self) -> None:
        self._pool.close()

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._pool.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                logger.info("SQL %s", cur.statusmessage)
                return [dict(row) for row in cur.fetchall()]

    def _execute(self, sql: str, params: tuple = ()) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                logger.info("SQL %s", cur.statusmessage)

    def search_client(self, phone_number: Any) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM main.client WHERE phone = %s",
            (phone_number,),
        )

    def insert_client_data(
        self, phone_number: Any, name: str = "None", surname: str = "None"
    ) -> int | None:
        with self._pool.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO main.client (phone, name, surname, add_time) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (phone_number, name, surname, datetime.date.today()),
                )
                logger.info("SQL %s", cur.statusmessage)
                row = cur.fetchone()
        if row is None:
            return None
        return int(row["id"])

    def show_all_clients(self) -> list[dict]:
        return self._fetch_all(
            "SELECT name, surname, id AS client, phone, add_time, false AS select "
            "FROM main.client ORDER BY add_time"
        )

    def select_last_client(self, number_client: int = 0) -> list[dict]:
        sql = (
            "SELECT c.id AS client, c.phone, MAX(s.date), c.name, c.surname "
            "FROM main.schedule_participant sp "
            "JOIN main.schedule s ON s.id = sp.schedule_id "
            "JOIN main.client c ON c.id = sp.client_id "
            "GROUP BY c.id, c.phone, c.name, c.surname "
            "ORDER BY MAX(s.date) DESC"
        )
        params: tuple = ()
        if number_client != 0:
            sql += " LIMIT %s"
            params = (number_client,)
        return self._fetch_all(sql, params)

    def list_all_train(self, group: bool) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM main.trains WHERE group_train = %s",
            (group,),
        )

    def get_train(self, train_id: Any) -> dict | None:
        rows = self._fetch_all(
            "SELECT * FROM main.trains WHERE id = %s",
            (train_id,),
        )
        return rows[0] if rows else None

    def select_time_at_data(self, date: Any) -> list:
        rows = self._fetch_all(
            "SELECT time FROM main.schedule WHERE date = %s",
            (date,),
        )
        return [row["time"] for row in rows]

    def get_schedule_at(self, date: Any, time: Any) -> dict | None:
        rows = self._fetch_all(
            "SELECT * FROM main.schedule WHERE date = %s AND time = %s",
            (date, time),
        )
        return rows[0] if rows else None

    def get_schedule_participants(self, schedule_id: Any) -> list[int]:
        rows = self._fetch_all(
            "SELECT client_id FROM main.schedule_participant "
            "WHERE schedule_id = %s ORDER BY client_id",
            (schedule_id,),
        )
        return [int(row["client_id"]) for row in rows]

    def insert_in_schedule(
        self,
        date: Any,
        client_id: Any,
        participant_ids: Any,
        time: Any,
        rent_debt: Any,
        type_train: Any,
        is_group: Any,
        train_price: Any,
        type_train_id: Any,
        set_is_complete_true: Any = False,
        accounting_id: Any = None,
    ) -> None:
        participants = _as_id_list(participant_ids)
        with self._pool.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                price = train_price
                if price is None and client_id is not None:
                    cur.execute(
                        "SELECT price FROM main.price "
                        "WHERE client_id = %s AND date <= %s "
                        "ORDER BY date DESC LIMIT 1",
                        (client_id, date),
                    )
                    logger.info("SQL %s", cur.statusmessage)
                    price_row = cur.fetchone()
                    price = price_row["price"] if price_row else None
                cur.execute(
                    "INSERT INTO main.schedule "
                    "(price, spend, date, time, rent_debt, type_train, "
                    "client_id, is_group, type_train_id, accounting_id) "
                    "VALUES (%s, False, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "RETURNING id",
                    (
                        price,
                        date,
                        time,
                        rent_debt,
                        type_train,
                        client_id,
                        is_group,
                        type_train_id,
                        accounting_id,
                    ),
                )
                logger.info("SQL %s", cur.statusmessage)
                inserted = cur.fetchone()
                schedule_id = inserted["id"] if inserted else None
                for participant_id in participants:
                    cur.execute(
                        "INSERT INTO main.schedule_participant "
                        "(schedule_id, client_id) VALUES (%s, %s)",
                        (schedule_id, participant_id),
                    )
                    logger.info("SQL %s", cur.statusmessage)
                if set_is_complete_true is not False and set_is_complete_true is not None:
                    cur.execute(
                        "UPDATE main.accounting SET is_complete = true WHERE id = %s",
                        (set_is_complete_true,),
                    )
                    logger.info("SQL %s", cur.statusmessage)

    def insert_in_accounting(
        self,
        client_id: Any,
        summ: Any,
        count_train: Any,
        price_per_train: Any,
        type_train_id: Any,
    ) -> None:
        self._execute(
            "INSERT INTO main.accounting "
            "(client_id, summ, count_train, updated_at, created_at, "
            "price_per_train, type_train_id) "
            f"VALUES (%s, %s, %s, {ACCOUNTING_NOW_SQL}, {ACCOUNTING_NOW_SQL}, %s, %s)",
            (client_id, summ, count_train, price_per_train, type_train_id),
        )

    def get_active_prepaid_for_client(
        self, client_id: Any, type_train_id: Any
    ) -> list[dict]:
        return self._fetch_all(
            "SELECT x.* FROM main.accounting x "
            "WHERE client_id = %s AND type_train_id = %s AND is_complete = False",
            (client_id, type_train_id),
        )

    def get_count_prepaid_train(
        self, client_id: Any, type_train_id: Any
    ) -> list[dict]:
        return self._fetch_all(
            "SELECT a.count_train, count(s.id) AS count "
            "FROM main.accounting a "
            "LEFT JOIN main.schedule s ON s.accounting_id = a.id "
            "WHERE a.client_id = %s "
            "AND a.type_train_id = %s "
            "AND a.is_complete = False "
            "GROUP BY a.id, a.count_train",
            (client_id, type_train_id),
        )

    def get_last_price_for_train(
        self, client_id: Any, type_train_id: Any
    ) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM main.schedule "
            "WHERE client_id = %s AND type_train_id = %s "
            "ORDER BY add_time DESC "
            "LIMIT 4",
            (client_id, type_train_id),
        )

    def get_incom_all_month_balance(self) -> list[dict]:
        return self._fetch_all(
            "SELECT "
            "sum(price) as total_sum, "
            "sum(rent_debt) as sum_rent, "
            "(sum(price) - sum(rent_debt)) as income, "
            "DATE_TRUNC('month', date) AS month, "
            "DATE_TRUNC('year', date) AS year "
            "FROM main.schedule GROUP BY month, year "
            "ORDER BY month ASC, year DESC"
        )
