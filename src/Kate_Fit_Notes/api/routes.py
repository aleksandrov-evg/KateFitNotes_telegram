"""Роуты ресурсов: клиенты, типы, слоты, записи, предоплаты, отчёт."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.Kate_Fit_Notes.api.auth import require_user
from src.Kate_Fit_Notes.api.deps import (
    get_booking_service,
    get_client_service,
    get_prepaid_service,
    get_report_service,
)
from src.Kate_Fit_Notes.api.schemas import (
    BookingOut,
    BookingPage,
    ClientCreate,
    ClientOut,
    ClientPage,
    GroupBookingIn,
    MonthReportOut,
    PersonalBookingIn,
    PrepaidIn,
    PrepaidOut,
    PrepaidPage,
    SlotListOut,
    TrainTypeOut,
)
from src.Kate_Fit_Notes.api.serialize import (
    booking_out,
    client_out,
    month_report_out,
    prepaid_out,
    slot_label,
    train_type_out,
)
from src.Kate_Fit_Notes.services.booking import BookingService
from src.Kate_Fit_Notes.services.clients import ClientService
from src.Kate_Fit_Notes.services.prepaid import PrepaidService
from src.Kate_Fit_Notes.services.report import ReportService

router = APIRouter(
    dependencies=[Depends(require_user)],
    responses={401: {"description": "не авторизован"}},
)


@router.get("/clients", response_model=ClientPage)
def list_clients(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ClientService = Depends(get_client_service),
) -> ClientPage:
    page = service.list_page(q=q, limit=limit, offset=offset)
    return ClientPage(
        items=[client_out(row) for row in page["items"]],
        total=page["total"],
        limit=page["limit"],
        offset=page["offset"],
    )


@router.post("/clients", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientCreate,
    service: ClientService = Depends(get_client_service),
) -> ClientOut:
    created = service.create(body.phone, body.name, body.surname)
    return client_out(created)


@router.get("/clients/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    service: ClientService = Depends(get_client_service),
) -> ClientOut:
    row = service.get(client_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="клиент не найден")
    return client_out(row)


@router.get("/train-types", response_model=list[TrainTypeOut])
def list_train_types(
    group: bool | None = Query(default=None),
    service: BookingService = Depends(get_booking_service),
) -> list[TrainTypeOut]:
    return [train_type_out(row) for row in service.list_train_types(group)]


@router.get("/slots", response_model=SlotListOut)
def list_slots(
    session_date: date = Query(alias="date"),
    service: BookingService = Depends(get_booking_service),
) -> SlotListOut:
    slots = service.list_available_slots(session_date)
    return SlotListOut(date=session_date, slots=[slot_label(slot) for slot in slots])


@router.get("/bookings", response_model=BookingPage)
def list_bookings(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    client_id: int | None = Query(default=None),
    updated_since: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: BookingService = Depends(get_booking_service),
) -> BookingPage:
    page = service.list_bookings(
        date_from=date_from,
        date_to=date_to,
        client_id=client_id,
        updated_since=updated_since,
        limit=limit,
        offset=offset,
    )
    return BookingPage(
        items=[booking_out(row) for row in page["items"]],
        total=page["total"],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/bookings/personal",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "слот уже занят"}},
)
def book_personal(
    body: PersonalBookingIn,
    service: BookingService = Depends(get_booking_service),
) -> BookingOut:
    booked = service.book_personal(
        client_id=body.client_id,
        type_train_id=body.type_train_id,
        session_date=body.date,
        session_time=body.time,
        price=body.price,
    )
    return booking_out(booked)


@router.post(
    "/bookings/group",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
)
def book_group(
    body: GroupBookingIn,
    service: BookingService = Depends(get_booking_service),
) -> BookingOut:
    booked = service.book_group(
        client_ids=body.client_ids,
        type_train_id=body.type_train_id,
        session_date=body.date,
        session_time=body.time,
        price=body.price,
    )
    return booking_out(booked)


@router.get("/prepaid", response_model=PrepaidPage)
def list_prepaid(
    client_id: int | None = Query(default=None),
    active: bool | None = Query(default=None),
    updated_since: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: PrepaidService = Depends(get_prepaid_service),
) -> PrepaidPage:
    page = service.list_packages(
        client_id=client_id,
        active=active,
        updated_since=updated_since,
        limit=limit,
        offset=offset,
    )
    return PrepaidPage(
        items=[prepaid_out(row) for row in page["items"]],
        total=page["total"],
        limit=limit,
        offset=offset,
    )


@router.post("/prepaid", response_model=PrepaidOut, status_code=status.HTTP_201_CREATED)
def add_prepaid(
    body: PrepaidIn,
    service: PrepaidService = Depends(get_prepaid_service),
) -> PrepaidOut:
    created = service.add_package(
        client_id=body.client_id,
        type_train_id=body.type_train_id,
        summ=body.summ,
        count=body.count,
    )
    return prepaid_out(created)


@router.get("/reports/monthly", response_model=list[MonthReportOut] | MonthReportOut)
def monthly_report(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    service: ReportService = Depends(get_report_service),
) -> list[MonthReportOut] | MonthReportOut:
    if year is not None and month is not None:
        return month_report_out(service.monthly_income(year, month))
    return [month_report_out(row) for row in service.monthly_report()]
