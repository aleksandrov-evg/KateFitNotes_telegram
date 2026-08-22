"""Смоук: миграция создаёт таблицы и колонки как в дампе Kate_fitness."""

REQUIRED_TABLES = ("client", "trains", "schedule", "accounting", "price", "test")


def test_main_tables_exist_after_migration(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            """
        )
        found = {row[0] for row in cur.fetchall()}
    assert found == set(REQUIRED_TABLES)
    assert "payment" not in found


def test_schedule_and_client_columns(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = 'schedule'
              AND column_name IN ('id', 'studio', 'client_list', 'price')
            """
        )
        schedule_cols = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = 'client'
              AND column_name = 'inactive'
            """
        )
        inactive = cur.fetchone()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = 'accounting'
              AND column_name = 'comment'
            """
        )
        comment = cur.fetchone()
    assert schedule_cols["id"] == "int4"
    assert schedule_cols["studio"] == "text"
    assert schedule_cols["client_list"] == "_int8"
    assert schedule_cols["price"] == "float4"
    assert inactive is not None
    assert comment is not None


def test_client_pk_and_schedule_unique(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'main'
              AND tc.table_name = 'client'
              AND tc.constraint_type = 'PRIMARY KEY'
            """
        )
        pk = [row[0] for row in cur.fetchall()]
        cur.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'main'
              AND tc.constraint_name = 'schedule_unique'
            ORDER BY kcu.ordinal_position
            """
        )
        unique_cols = [row[0] for row in cur.fetchall()]
    assert pk == ["phone"]
    assert unique_cols == ["date", "time", "client"]
