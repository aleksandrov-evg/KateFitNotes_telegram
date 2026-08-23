"""Тонкие обёртки над PostgresRepository. Импорт вызывает load_settings()."""

from src.Kate_Fit_Notes.repository import PostgresRepository
from src.Kate_Fit_Notes.settings import load_settings

_repo = PostgresRepository.from_settings(load_settings())


def search_client(phone_number):
    return _repo.search_client(phone_number)


def insert_client_data(phone_number, name="None", surname="None"):
    return _repo.insert_client_data(phone_number, name, surname)


def list_all_train(group):
    return _repo.list_all_train(group)


def show_all_clients():
    return _repo.show_all_clients()


def select_last_client(number_client=0):
    return _repo.select_last_client(number_client)


def select_time_at_data(date):
    return _repo.select_time_at_data(date)


def insert_in_schedule(
    date,
    client_id,
    client_list,
    time,
    rent_debt,
    type_train,
    is_group,
    train_price,
    type_train_id,
    set_is_complete_true=False,
):
    return _repo.insert_in_schedule(
        date,
        client_id,
        client_list,
        time,
        rent_debt,
        type_train,
        is_group,
        train_price,
        type_train_id,
        set_is_complete_true,
    )


def get_incom_all_month_balance():
    return _repo.get_incom_all_month_balance()


def insert_in_accounting(client_id, summ, count_train, price_per_train, type_train_id):
    return _repo.insert_in_accounting(
        client_id, summ, count_train, price_per_train, type_train_id
    )


def get_active_prepaid_for_client(client_id, type_train_id):
    return _repo.get_active_prepaid_for_client(client_id, type_train_id)


def get_count_prepaid_train(client_id, type_train_id):
    return _repo.get_count_prepaid_train(client_id, type_train_id)


def get_last_price_for_train(client_id, type_train_id):
    return _repo.get_last_price_for_train(client_id, type_train_id)
