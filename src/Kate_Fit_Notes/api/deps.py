"""Зависимости FastAPI: сервисы из app.state."""

from __future__ import annotations

from fastapi import Request

from src.Kate_Fit_Notes.services.booking import BookingService
from src.Kate_Fit_Notes.services.clients import ClientService
from src.Kate_Fit_Notes.services.prepaid import PrepaidService
from src.Kate_Fit_Notes.services.report import ReportService
from src.Kate_Fit_Notes.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_client_service(request: Request) -> ClientService:
    return request.app.state.client_service


def get_booking_service(request: Request) -> BookingService:
    return request.app.state.booking_service


def get_prepaid_service(request: Request) -> PrepaidService:
    return request.app.state.prepaid_service


def get_report_service(request: Request) -> ReportService:
    return request.app.state.report_service
