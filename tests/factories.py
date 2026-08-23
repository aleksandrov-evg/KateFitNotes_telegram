"""Фабрики строк для тестов. Параметризованный SQL, без sql.py."""

from datetime import date, datetime, time


def make_client(conn, phone=9001112233, name="Тест", surname="Клиентов", add_time=None):
    added = add_time or date.today()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO main.client (phone, name, surname, add_time) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (phone, name, surname, added),
        )
        row = cur.fetchone()
    conn.commit()
    return {
        "id": row[0],
        "client": row[0],
        "phone": phone,
        "name": name,
        "surname": surname,
        "add_time": added,
    }


def make_train(conn, type_train="Доп. персональная", group_train=False, rent_debt=0):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO main.trains (type_train, group_train, rent_debt) "
            "VALUES (%s, %s, %s) RETURNING id",
            (type_train, group_train, rent_debt),
        )
        row = cur.fetchone()
    conn.commit()
    return {
        "id": row[0],
        "type_train": type_train,
        "group_train": group_train,
        "rent_debt": rent_debt,
    }


def make_schedule(
    conn,
    client_id,
    session_date=None,
    session_time=None,
    type_train="персональная",
    type_train_id=1,
    price=1000,
    rent_debt=0,
    is_group=False,
    participants=None,
    accounting_id=None,
):
    session_date = session_date or date.today()
    session_time = session_time or time(10, 0)
    if participants is None:
        participants = [] if is_group or client_id is None else [client_id]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO main.schedule "
            "(price, spend, date, time, rent_debt, type_train, client_id, "
            "is_group, type_train_id, accounting_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                price,
                False,
                session_date,
                session_time,
                rent_debt,
                type_train,
                client_id,
                is_group,
                type_train_id,
                accounting_id,
            ),
        )
        row = cur.fetchone()
        schedule_id = row[0]
        for participant_id in participants:
            cur.execute(
                "INSERT INTO main.schedule_participant "
                "(schedule_id, client_id) VALUES (%s, %s)",
                (schedule_id, participant_id),
            )
    conn.commit()
    return {
        "id": schedule_id,
        "client_id": client_id,
        "date": session_date,
        "time": session_time,
        "participants": list(participants),
        "accounting_id": accounting_id,
    }


def make_accounting(
    conn,
    client_id,
    type_train_id,
    summ=10000,
    count_train=10,
    price_per_train=1000,
    is_complete=False,
    created_at=None,
):
    created = created_at or datetime(2020, 1, 1)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO main.accounting "
            "(client_id, summ, count_train, price_per_train, type_train_id, "
            "is_complete, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                client_id,
                summ,
                count_train,
                price_per_train,
                type_train_id,
                is_complete,
                created,
                created,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return {
        "id": row[0],
        "client_id": client_id,
        "type_train_id": type_train_id,
        "summ": summ,
        "count_train": count_train,
        "price_per_train": price_per_train,
        "is_complete": is_complete,
    }
