"""Фабрики строк для тестов. Параметризованный SQL, без sql.py."""

from datetime import date


def make_client(conn, phone=9001112233, name="Тест", surname="Клиентов"):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO main.client (phone, name, surname, add_time) "
            "VALUES (%s, %s, %s, %s)",
            (phone, name, surname, date.today()),
        )
    conn.commit()
    return {"phone": phone, "name": name, "surname": surname}


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
