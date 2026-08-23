"""Репозиторий PostgreSQL: параметризованный SQL, list[dict]. Без load_settings при импорте."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Protocol

from psycopg2.extras import RealDictCursor

from src.Kate_Fit_Notes.db import ConnectionPool
from src.Kate_Fit_Notes.domain import ACCOUNTING_NOW_SQL
from src.Kate_Fit_Notes.settings import Settings

logger = logging.getLogger(__name__)


class KateFitRepository(Protocol):
    def search_client(self, phone_number: Any) -> list[dict]: ...

    def insert_client_data(
        self, phone_number: Any, name: str = "None", surname: str = "None"
    ) -> None: ...

    def show_all_clients(self) -> list[dict]: ...

    def select_last_client(self, number_client: int = 0) -> list[dict]: ...

    def list_all_train(self, group: bool) -> list[dict]: ...

    def get_train(self, train_id: Any) -> dict | None: ...

    def select_time_at_data(self, date: Any) -> list: ...

    def get_schedule_at(self, date: Any, time: Any) -> dict | None: ...

    def insert_in_schedule(
        self,
        date: Any,
        client_id: Any,
        client_list: Any,
        time: Any,
        rent_debt: Any,
        type_train: Any,
        is_group: Any,
        train_price: Any,
        type_train_id: Any,
        set_is_complete_true: Any = False,
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
    ) -> None:
        self._execute(
            "INSERT INTO main.client (phone, name, surname, add_time) "
            "VALUES (%s, %s, %s, %s)",
            (phone_number, name, surname, datetime.date.today()),
        )

    def show_all_clients(self) -> list[dict]:
        return self._fetch_all(
            "SELECT name, surname, phone AS client, add_time, false AS select "
            "FROM main.client ORDER BY add_time"
        )

    def select_last_client(self, number_client: int = 0) -> list[dict]:
        sql = (
            "SELECT main.schedule.client, MAX(main.schedule.date), "
            "main.client.name, main.client.surname "
            "FROM main.schedule LEFT JOIN main.client "
            "ON main.schedule.client = main.client.phone "
            "GROUP BY client, main.client.name, main.client.surname "
            "ORDER BY MAX(date) DESC"
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

    def insert_in_schedule(
        self,
        date: Any,
        client_id: Any,
        client_list: Any,
        time: Any,
        rent_debt: Any,
        type_train: Any,
        is_group: Any,
        train_price: Any,
        type_train_id: Any,
        set_is_complete_true: Any = False,
    ) -> None:
        with self._pool.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                price = train_price
                if price is None:
                    cur.execute(
                        "SELECT price FROM main.price "
                        "WHERE client = %s AND date <= %s "
                        "ORDER BY date DESC LIMIT 1",
                        (client_id, date),
                    )
                    logger.info("SQL %s", cur.statusmessage)
                    price_row = cur.fetchone()
                    price = price_row["price"] if price_row else None
                cur.execute(
                    "INSERT INTO main.schedule "
                    "(price, spend, date, time, rent_debt, type_train, "
                    "client, client_list, is_group, type_train_id) "
                    "VALUES (%s, False, %s, %s, %s, %s, %s, %s::bigint[], %s, %s)",
                    (
                        price,
                        date,
                        time,
                        rent_debt,
                        type_train,
                        client_id,
                        client_list,
                        is_group,
                        type_train_id,
                    ),
                )
                logger.info("SQL %s", cur.statusmessage)
                if set_is_complete_true:
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
            "SELECT a.count_train, count(s.client) "
            "FROM main.accounting a RIGHT JOIN main.schedule s "
            "ON a.client_id = s.client "
            "WHERE s.client = %s "
            "AND a.created_at <= s.add_time "
            "AND a.is_complete = False "
            "AND s.type_train_id = %s "
            "GROUP BY a.count_train",
            (client_id, type_train_id),
        )

    def get_last_price_for_train(
        self, client_id: Any, type_train_id: Any
    ) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM main.schedule "
            "WHERE client = %s AND type_train_id = %s "
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
