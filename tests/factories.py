"""Фабрики строк для тестов. Параметризованный SQL, без sql.py."""

from datetime import date, time


def make_client(conn, phone=9001112233, name="Тест", surname="Клиентов", add_time=None):
    added = add_time or date.today()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO main.client (phone, name, surname, add_time) "
            "VALUES (%s, %s, %s, %s)",
            (phone, name, surname, added),
        )
    conn.commit()
    return {"phone": phone, "name": name, "surname": surname, "add_time": added}


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
    client,
    session_date=None,
    session_time=None,
    type_train="персональная",
    type_train_id=1,
    price=1000,
    rent_debt=0,
    is_group=False,
    client_list=None,
):
    session_date = session_date or date.today()
    session_time = session_time or time(10, 0)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO main.schedule "
            "(price, spend, date, time, rent_debt, type_train, client, "
            "client_list, is_group, type_train_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                price,
                False,
                session_date,
                session_time,
                rent_debt,
                type_train,
                client,
                client_list,
                is_group,
                type_train_id,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return {
        "id": row[0],
        "client": client,
        "date": session_date,
        "time": session_time,
    }
