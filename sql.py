import configparser
import psycopg2
from psycopg2 import OperationalError

config = configparser.ConfigParser()
config.read("config.ini")


def create_connection():
    connection = None
    try:
        connection = psycopg2.connect(
            database=config["sql"]["database"],
            user=config["sql"]["user"],
            password=config["sql"]["password"],
            host=config["sql"]["host"],
            port=config["sql"]["port"],
        )
        print("Подключение к базе данных PostgreSQL прошло успешно")
    except OperationalError as e:
        print(f"Произошла ошибка '{e}'")
    return connection
