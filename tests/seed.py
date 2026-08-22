"""Seed справочника типов тренировок из дампа Kate_fitness — только для тестов."""

from datetime import date

# COPY main.trains из backups/cluster_2026-08-22_1723.sql (17 строк, ids 1–17).
SEED_TRAINS = (
    ("мягкий фитнесс 1 чел", 1, False, 1400, date(2023, 4, 18)),
    ("мягкий фитнесс 2 чел", 2, True, 2100, date(2023, 4, 18)),
    ("мягкий фитнесс 3 чел", 3, True, 2500, date(2023, 4, 18)),
    ("мягкий фитнесс 4 чел", 4, True, 2800, date(2023, 4, 18)),
    ("силовая 1 чел", 5, False, 1400, date(2023, 4, 18)),
    ("силовая 2 чел", 6, True, 2100, date(2023, 4, 18)),
    ("силовая 3 чел", 7, True, 2500, date(2023, 4, 18)),
    ("силовая 4 чел", 8, True, 2800, date(2023, 4, 18)),
    ("гамак 1 чел", 9, False, 1500, date(2023, 4, 18)),
    ("гамак 2 чел", 10, True, 2600, date(2023, 4, 18)),
    ("надомница", 11, False, 0, date(2023, 4, 25)),
    ("гамак мать+дочь", 12, False, 2600, date(2024, 2, 6)),
    ("надомница 2 чел", 13, True, 0, date(2024, 2, 6)),
    ("Тейпирование", 14, False, 0, date(2024, 4, 23)),
    ("Детский сайкл", 15, True, 0, date(2024, 4, 23)),
    ("мягкий фитнесс 2 чел (абонимент)", 16, False, 2100, date(2024, 11, 18)),
    ("[дом] Реформер", 17, False, 0, date(2026, 8, 22)),
)

INSERT_TRAIN = (
    "INSERT INTO main.trains (type_train, id, group_train, rent_debt, date) "
    "VALUES (%s, %s, %s, %s, %s)"
)

TRUNCATE_MAIN = """
TRUNCATE TABLE
    main.client,
    main.trains,
    main.schedule,
    main.accounting,
    main.price,
    main.test
RESTART IDENTITY CASCADE
"""


def seed_trains(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany(INSERT_TRAIN, SEED_TRAINS)
        cur.execute("SELECT pg_catalog.setval('main.trains_id_seq', 17, true)")
    conn.commit()


def truncate_main(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(TRUNCATE_MAIN)
    conn.commit()
