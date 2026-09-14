"""Начальный снимок схемы main.* as-is.

Снято из backups/kate_fitness_schema.sql (дамп БД Kate_fitness), не из sql.py.
Модель не меняется: client = телефон, client_list — bigint[].
OWNER и прод-setval не копируются.

Revision ID: 0001_initial_as_is
Revises:
Create Date: 2026-08-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial_as_is"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS main")
    op.execute(
        """
        CREATE TABLE main.accounting (
            client_id bigint,
            type_action text,
            summ integer,
            count_train integer,
            price_per_train integer,
            date timestamp without time zone,
            comment text,
            is_complete boolean DEFAULT false NOT NULL,
            updated_at timestamp without time zone,
            created_at timestamp without time zone,
            id bigint NOT NULL,
            type_train_id integer
        )
        """
    )
    op.execute(
        """
        ALTER TABLE main.accounting ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
            SEQUENCE NAME main.accounting_id_seq
            START WITH 0
            INCREMENT BY 1
            MINVALUE 0
            NO MAXVALUE
            CACHE 1
        )
        """
    )
    op.execute(
        """
        CREATE TABLE main.client (
            name text,
            surname text,
            phone bigint NOT NULL,
            add_time date,
            inactive boolean DEFAULT false
        )
        """
    )
    op.execute(
        """
        CREATE TABLE main.price (
            client bigint,
            price real NOT NULL,
            date date,
            id integer NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE SEQUENCE main.price_id_seq
            AS integer
            START WITH 1
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1
        """
    )
    op.execute("ALTER SEQUENCE main.price_id_seq OWNED BY main.price.id")
    op.execute(
        """
        CREATE TABLE main.schedule (
            price real,
            spend boolean,
            studio text,
            date date,
            "time" time without time zone,
            rent_debt integer,
            type_train text,
            id integer NOT NULL,
            client bigint,
            client_list bigint[],
            is_group boolean,
            add_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP(0),
            type_train_id integer
        )
        """
    )
    op.execute(
        """
        CREATE SEQUENCE main.schedule_id_seq
            AS integer
            START WITH 1
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1
        """
    )
    op.execute("ALTER SEQUENCE main.schedule_id_seq OWNED BY main.schedule.id")
    op.execute(
        """
        CREATE TABLE main.test (
            dig_array bigint[]
        )
        """
    )
    op.execute(
        """
        CREATE TABLE main.trains (
            type_train text NOT NULL,
            id integer NOT NULL,
            group_train boolean,
            rent_debt integer,
            date date
        )
        """
    )
    op.execute(
        """
        CREATE SEQUENCE main.trains_id_seq
            AS integer
            START WITH 1
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1
        """
    )
    op.execute("ALTER SEQUENCE main.trains_id_seq OWNED BY main.trains.id")
    op.execute(
        "ALTER TABLE ONLY main.price "
        "ALTER COLUMN id SET DEFAULT nextval('main.price_id_seq'::regclass)"
    )
    op.execute(
        "ALTER TABLE ONLY main.schedule "
        "ALTER COLUMN id SET DEFAULT nextval('main.schedule_id_seq'::regclass)"
    )
    op.execute(
        "ALTER TABLE ONLY main.trains "
        "ALTER COLUMN id SET DEFAULT nextval('main.trains_id_seq'::regclass)"
    )
    op.execute(
        "ALTER TABLE ONLY main.accounting ADD CONSTRAINT accounting_pk PRIMARY KEY (id)"
    )
    op.execute(
        "ALTER TABLE ONLY main.client ADD CONSTRAINT client_pkey PRIMARY KEY (phone)"
    )
    op.execute(
        "ALTER TABLE ONLY main.price ADD CONSTRAINT price_pkey PRIMARY KEY (id)"
    )
    op.execute(
        "ALTER TABLE ONLY main.schedule ADD CONSTRAINT schedule_pkey PRIMARY KEY (id)"
    )
    op.execute(
        'ALTER TABLE ONLY main.schedule '
        'ADD CONSTRAINT schedule_unique UNIQUE (date, "time", client)'
    )
    op.execute(
        "ALTER TABLE ONLY main.trains ADD CONSTRAINT trains_pkey PRIMARY KEY (id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS main.test")
    op.execute("DROP TABLE IF EXISTS main.schedule")
    op.execute("DROP TABLE IF EXISTS main.price")
    op.execute("DROP TABLE IF EXISTS main.accounting")
    op.execute("DROP TABLE IF EXISTS main.trains")
    op.execute("DROP TABLE IF EXISTS main.client")
    op.execute("DROP SCHEMA IF EXISTS main")
