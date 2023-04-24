import sql
import psycopg2
import os
import configparser


def test_create_connection():
    config = configparser.ConfigParser()
    config.read("config.ini")

    connection = psycopg2.connect(
        database=config["sql"]["database"],
        user=os.getenv('TG_ACCOUNT'),
        password=os.getenv('TG_PASS'),
        host=config["sql"]["ip"],
        port=config["sql"]["port"],
    )
    assert connection is not None


def test_connection_sql():
    assert sql.create_connection() is not None


def test_search_client():
    query = sql.search_client(0)
    assert int(query[1]) != 0

