"""Фабрика FastAPI-приложения. Импорт не требует TG_TOKEN и не стартует бота."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.Kate_Fit_Notes.api.auth import router as auth_router
from src.Kate_Fit_Notes.api.routes import router as api_router
from src.Kate_Fit_Notes.api.schemas import HealthOut
from src.Kate_Fit_Notes.repository import KateFitRepository, PostgresRepository
from src.Kate_Fit_Notes.services.booking import BookingService
from src.Kate_Fit_Notes.services.clients import ClientService
from src.Kate_Fit_Notes.services.errors import (
    DuplicateClientError,
    EmptyParticipantsError,
    InvalidPhoneError,
    InvalidPrepaidError,
    InvalidTrainTypeError,
    MultiplePrepaidError,
    SlotTakenError,
)
from src.Kate_Fit_Notes.services.prepaid import PrepaidService
from src.Kate_Fit_Notes.services.report import ReportService
from src.Kate_Fit_Notes.settings import ConfigError, Settings, load_settings

_UNPROCESSABLE = (
    InvalidPhoneError,
    InvalidPrepaidError,
    InvalidTrainTypeError,
    EmptyParticipantsError,
)
_CONFLICT = (
    DuplicateClientError,
    SlotTakenError,
    MultiplePrepaidError,
)


def create_app(settings: Settings, repository: KateFitRepository) -> FastAPI:
    if not settings.api_user or not settings.api_password or not settings.api_jwt_secret:
        raise ConfigError(
            "Нет обязательных полей API: API_USER, API_PASSWORD, API_JWT_SECRET"
        )

    app = FastAPI(title="Kate Fit Notes API", version="0.1.0")
    app.state.settings = settings
    app.state.repository = repository
    app.state.client_service = ClientService(repository)
    app.state.booking_service = BookingService(repository)
    app.state.prepaid_service = PrepaidService(repository)
    app.state.report_service = ReportService(repository)

    def _json_error(status_code: int):
        async def handler(_request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=status_code)

        return handler

    for exc_type in _UNPROCESSABLE:
        app.add_exception_handler(exc_type, _json_error(422))
    for exc_type in _CONFLICT:
        app.add_exception_handler(exc_type, _json_error(409))

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut()

    return app


def app_from_env() -> FastAPI:
    settings = load_settings()
    return create_app(settings, PostgresRepository.from_settings(settings))
