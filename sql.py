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


def insert_client_data(phone_number, name="None", surname="None"):

    insert_query = f"INSERT INTO main.client (phone, name, surname) VALUES ({phone_number},'{name}','{surname}')"

    connection = create_connection()
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute(insert_query)


