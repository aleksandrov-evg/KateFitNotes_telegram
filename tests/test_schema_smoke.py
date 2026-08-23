"""Смоук: миграция head создаёт схему модели сайта (этап 11)."""

REQUIRED_TABLES = (
    "client",
    "trains",
    "schedule",
    "schedule_participant",
    "accounting",
    "price",
    "test",
)


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
              AND column_name IN ('id', 'studio', 'client_list', 'client_id',
                                  'accounting_id', 'price')
            """
        )
        schedule_cols = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute(
            """
            SELECT column_name, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = 'client'
              AND column_name IN ('id', 'phone', 'inactive')
            """
        )
        client_cols = {row[0]: row[1] for row in cur.fetchall()}
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
    assert schedule_cols["client_id"] == "int4"
    assert schedule_cols["accounting_id"] == "int8"
    assert schedule_cols["price"] == "float4"
    assert "client_list" not in schedule_cols
    assert client_cols["id"] == "int4"
    assert client_cols["phone"] == "int8"
    assert "inactive" in client_cols
    assert comment is not None


def test_client_pk_phone_unique_and_schedule_unique(db_conn):
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
              AND tc.table_name = 'client'
              AND tc.constraint_type = 'UNIQUE'
            ORDER BY kcu.ordinal_position
            """
        )
        unique_phone = [row[0] for row in cur.fetchall()]
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
    assert pk == ["id"]
    assert unique_phone == ["phone"]
    assert unique_cols == ["date", "time"]
