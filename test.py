import sql
import psycopg2
import os


# def test_create_connection():
#     connection = psycopg2.connect(
#         database='pg_db',
#         user=os.environ['TG_ACCOUNT'],
#         password=os.environ['TG_PASS'],
#         host='172.22.0.3',
#         port=config["sql"]["port"],
#     )
#     assert connection is not None


def test_connection_sql():
    assert sql.create_connection() is not None


def test_search_client():
    query = sql.search_client(0)
    assert int(query[1]) != 0

