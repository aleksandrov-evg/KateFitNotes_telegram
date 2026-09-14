-- Schema-only снимок БД Kate_fitness.
-- Снято из backups/cluster_2026-08-22_1723.sql (блок Kate_fitness, до Project_KAT).
-- Без COPY данных, без OWNER, без CREATE DATABASE.
-- Накатывать через Alembic, не этим файлом на прод.

CREATE SCHEMA IF NOT EXISTS main;

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
);

ALTER TABLE main.accounting ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME main.accounting_id_seq
    START WITH 0
    INCREMENT BY 1
    MINVALUE 0
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE main.client (
    name text,
    surname text,
    phone bigint NOT NULL,
    add_time date,
    inactive boolean DEFAULT false
);

CREATE TABLE main.price (
    client bigint,
    price real NOT NULL,
    date date,
    id integer NOT NULL
);

CREATE SEQUENCE main.price_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE main.price_id_seq OWNED BY main.price.id;

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
);

CREATE SEQUENCE main.schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE main.schedule_id_seq OWNED BY main.schedule.id;

CREATE TABLE main.test (
    dig_array bigint[]
);

CREATE TABLE main.trains (
    type_train text NOT NULL,
    id integer NOT NULL,
    group_train boolean,
    rent_debt integer,
    date date
);

CREATE SEQUENCE main.trains_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE main.trains_id_seq OWNED BY main.trains.id;

ALTER TABLE ONLY main.price ALTER COLUMN id SET DEFAULT nextval('main.price_id_seq'::regclass);
ALTER TABLE ONLY main.schedule ALTER COLUMN id SET DEFAULT nextval('main.schedule_id_seq'::regclass);
ALTER TABLE ONLY main.trains ALTER COLUMN id SET DEFAULT nextval('main.trains_id_seq'::regclass);

ALTER TABLE ONLY main.accounting
    ADD CONSTRAINT accounting_pk PRIMARY KEY (id);

ALTER TABLE ONLY main.client
    ADD CONSTRAINT client_pkey PRIMARY KEY (phone);

ALTER TABLE ONLY main.price
    ADD CONSTRAINT price_pkey PRIMARY KEY (id);

ALTER TABLE ONLY main.schedule
    ADD CONSTRAINT schedule_pkey PRIMARY KEY (id);

ALTER TABLE ONLY main.schedule
    ADD CONSTRAINT schedule_unique UNIQUE (date, "time", client);

ALTER TABLE ONLY main.trains
    ADD CONSTRAINT trains_pkey PRIMARY KEY (id);
