import configparser
import psycopg2
from psycopg2 import OperationalError

config = configparser.ConfigParser()
config.read("config.ini")


def execute_query(text_query: object) -> object:
    connection = create_connection()
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute(text_query)
    result_query = cursor.statusmessage.split(' ')
    if result_query[0] == 'SELECT':
        array_data = cursor.fetchall()
        column_name = []
        for i in cursor.description:
            column_name.append(i.name)
        result_list = []
        for x in array_data:
            result_list.append(dict(zip(column_name, x)))
        result_query.append(result_list)
        return result_query


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


def search_client(phone_number):
    text_query = f"SELECT * FROM main.client " \
                 f"WHERE phone = {phone_number}"
    find_client = execute_query(text_query)
    return find_client


def insert_client_data(phone_number, name="None", surname="None"):
    search_client(phone_number)
    text_query = f"INSERT INTO main.client (phone, name, surname) " \
                 f"VALUES ({phone_number},'{name}','{surname}')"
    execute_query(text_query)
