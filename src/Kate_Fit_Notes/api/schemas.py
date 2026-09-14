"""Pydantic-модели запросов и ответов API."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ClientCreate(BaseModel):
    phone: str
    name: str | None = "None"
    surname: str | None = "None"


class ClientOut(BaseModel):
    id: int
    phone: int
    name: str
    surname: str


class ClientPage(BaseModel):
    items: list[ClientOut]
    total: int
    limit: int
    offset: int


class TrainTypeOut(BaseModel):
    id: int
    type_train: str
    group_train: bool
    rent_debt: float | None = None


class SlotListOut(BaseModel):
    date: date
    slots: list[str]


class PersonalBookingIn(BaseModel):
    client_id: int
    type_train_id: int
    date: date
    time: time
    price: int | None = None


class GroupBookingIn(BaseModel):
    client_ids: list[int]
    type_train_id: int
    date: date
    time: time
    price: int | None = None


class BookingOut(BaseModel):
    client: int | None = None
    participants: list[int] | None = None
    date: date
    time: time
    price: float | None = None
    type_train_id: int
    accounting_id: int | None = None


class PrepaidIn(BaseModel):
    client_id: int
    type_train_id: int
    summ: int
    count: int


class PrepaidOut(BaseModel):
    client_id: int
    type_train_id: int
    summ: int
    count_train: int
    price_per_train: float


class MonthReportOut(BaseModel):
    income: float
    sum_rent: float
    total_sum: float
    month: date | None = None


class HealthOut(BaseModel):
    status: str = Field(default="ok")
