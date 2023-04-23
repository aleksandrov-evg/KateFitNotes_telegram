import sql
import psycopg2
import os


def test_create_connection():
    connection = psycopg2.connect(
        database='Kate_fitness_test',
        user=os.getenv('TG_ACCOUNT'),
        password=os.getenv('TG_PASS'),
        host=,
        port=,
    )
    assert connection is not None


def test_connection_sql():
    assert sql.create_connection() is not None


def test_search_client():
    query = sql.search_client(0)
    assert int(query[1]) != 0

