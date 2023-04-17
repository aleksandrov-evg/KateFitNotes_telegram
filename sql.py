import configparser
import psycopg2
from psycopg2 import OperationalError
import datetime
import os


config = configparser.ConfigParser()
config.read("config.ini")


if config["sql"]["host"] == '':
    try:
        db_ip = os.system("docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' pg_db")
        print(f'Ip адрес базы данных:{db_ip}')
    except:
        print('Хост Бд не найден')
else:
    db_ip = config["sql"]["host"]


def execute_query(text_query):
    connection = create_connection()
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute(text_query)
    print(f'[{datetime.datetime.now()}]Запрос с текстом <<{cursor.query}>> '
          f'выполнен с результатом <<{cursor.statusmessage}>>')
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
            user=os.environ['TG_ACCOUNT'],
            password=os.environ['TG_PASS'],
            host=db_ip,
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
    return execute_query(text_query)


def list_all_train(group):
    text_query = f"SELECT * FROM main.trains WHERE group_train = {group}"
    return execute_query(text_query)


def show_all_clients():
    text_query = f'SELECT name, surname, phone AS client, add_time, false AS select ' \
                 f'FROM main.client ORDER BY  add_time'
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


def insert_in_schedule(date, client_id, client_list, time, rent_debt, type_train):

    subquery_find_price = f"SELECT price FROM main.price " \
                          f"WHERE client = {client_id} and date <= '{date}' " \
                          f"ORDER BY date DESC LIMIT 1"

    text_query = f"INSERT INTO main.schedule (price, spend,date,time,rent_debt,type_train,client,client_list) " \
                 f"VALUES (({subquery_find_price}),False, '{date}','{time}',{rent_debt}, '{type_train}', {client_id}, '{client_list}')"
    return execute_query(text_query)


def insert_test_data(column, value):
    text_query = f"INSERT INTO main.test ({column}) " \
                 f"VALUES ('{value}')"
    return execute_query(text_query)


def insert_balance(client_id, date, type_operation, count, price):
    text_query = f"INSERT INTO main.payment (client_id, data, type, count, price) " \
                 f"VALUES ('{client_id, date, type_operation, count, price}')"

    return execute_query(text_query)

