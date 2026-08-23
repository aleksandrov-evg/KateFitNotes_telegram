"""Ошибки сценариев сервисов. Не путать валидацию с уникальностью."""


class InvalidPhoneError(ValueError):
    """Телефон не нормализуется в 10 цифр."""


class DuplicateClientError(ValueError):
    """Клиент с таким телефоном уже есть (PK phone)."""


class SlotTakenError(ValueError):
    """Дата и время уже заняты в расписании."""


class InvalidTrainTypeError(ValueError):
    """Тип тренировки не подходит для персональной записи."""


class MultiplePrepaidError(ValueError):
    """У клиента больше одного незакрытого пакета предоплаты."""

    def __init__(self, count: int, ids: list):
        self.count = count
        self.ids = ids
        super().__init__(f"у клиента {count} незакрытых предоплат")
