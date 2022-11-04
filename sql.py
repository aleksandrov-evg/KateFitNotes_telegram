import configparser
import psycopg2
from psycopg2 import OperationalError
import datetime

config = configparser.ConfigParser()
config.read("config.ini")


def execute_query(text_query):
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
        print(f"[{datetime.datetime.now()}]Подключение к базе данных PostgreSQL прошло успешно")
    except OperationalError as e:
        print(f"[{datetime.datetime.now()}]Произошла ошибка '{e}'")
    return connection


def search_client(phone_number):
    text_query = f"SELECT * FROM main.client " \
                 f"WHERE phone = {phone_number}"
    find_client = execute_query(text_query)
    return find_client


def insert_client_data(phone_number, name="None", surname="None"):
    search_client(phone_number)
    text_query = f"INSERT INTO main.client (phone, name, surname, add_time) " \
                 f"VALUES ({phone_number},'{name}','{surname}', '{datetime.date.today()}')"
    execute_query(text_query)


def list_all_train():
    text_query = f"SELECT type_train FROM main.trains"
    return execute_query(text_query)


def select_last_client(number_client=0):
    text_query = f"SELECT main.schedule.client, MAX (main.schedule.date), main.client.name, main.client.surname " \
                 f"FROM main.schedule LEFT JOIN main.client ON main.schedule.client = main.client.phone " \
                 f"GROUP BY client, main.client.name,  main.client.surname " \
                 f"ORDER BY MAX (date) DESC"
    if number_client != 0:
        text_query += f" LIMIT {number_client}"
    return execute_query(text_query)


def select_time_at_data(date):
    text_query = f"SELECT time FROM main.schedule WHERE date = '{date}'"

    return [i['time'] for i in execute_query(text_query)[2]]
