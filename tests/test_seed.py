"""Смоук: seed типов тренировок из дампа Kate_fitness."""

from tests.seed import SEED_TRAINS


def test_seed_trains_count_personal_and_group(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT type_train, group_train, rent_debt, location FROM main.trains"
        )
        rows = cur.fetchall()
    assert len(rows) == 17
    assert ("мягкий фитнесс 1 чел", False, 1400, "ter_fit") in rows
    assert ("мягкий фитнесс 2 чел", True, 2100, "ter_fit") in rows
    assert ("[дом] Реформер", False, 0, "home") in rows
    assert len(SEED_TRAINS) == 17


def test_make_client_factory(make_client, db_conn):
    client = make_client(phone=9123456789, name="Анна")
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT phone, name FROM main.client WHERE phone = %s",
            (client["phone"],),
        )
        row = cur.fetchone()
    assert row == (9123456789, "Анна")


def test_make_train_factory(make_train, db_conn):
    train = make_train(type_train="Стретчинг", group_train=True, rent_debt=500)
    assert train["id"] > 17
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT type_train, group_train, rent_debt FROM main.trains WHERE id = %s",
            (train["id"],),
        )
        row = cur.fetchone()
    assert row == ("Стретчинг", True, 500)
