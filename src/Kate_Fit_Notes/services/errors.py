"""Ошибки сценариев сервисов. Не путать валидацию с уникальностью."""


class InvalidPhoneError(ValueError):
    """Телефон не нормализуется в 10 цифр."""


class DuplicateClientError(ValueError):
    """Клиент с таким телефоном уже есть (PK phone)."""
