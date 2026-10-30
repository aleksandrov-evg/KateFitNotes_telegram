"""Фабрика FastAPI-приложения. Импорт не требует TG_TOKEN и не стартует бота."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.Kate_Fit_Notes.api.auth import router as auth_router
from src.Kate_Fit_Notes.api.routes import router as api_router
from src.Kate_Fit_Notes.api.request_log import RequestLogMiddleware
from src.Kate_Fit_Notes.api.schemas import HealthOut
from src.Kate_Fit_Notes.api.studio import StudioCrm, load_studio_settings, router as studio_router
from src.Kate_Fit_Notes.api.studio_payroll import router as payroll_router
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
from src.Kate_Fit_Notes.settings import ApiSettings, ConfigError, Settings, load_api_settings

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


def create_app(settings: Settings | ApiSettings, repository: KateFitRepository, studio_crm: StudioCrm | None = None) -> FastAPI:
    if not settings.api_user or not settings.api_password or not settings.api_jwt_secret:
        raise ConfigError(
            "Нет обязательных полей API: API_USER, API_PASSWORD, API_JWT_SECRET"
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            if studio_crm is not None:
                studio_crm.close()

    app = FastAPI(title="Kate Fit Notes API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestLogMiddleware)
    app.state.studio_crm = studio_crm
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
    app.include_router(studio_router, prefix="/api/v1")
    app.include_router(payroll_router, prefix="/api/v1")

    @app.get("/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut()

    return app


def app_from_env() -> FastAPI:
    settings = load_api_settings()
    studio_settings = load_studio_settings()
    studio_crm = StudioCrm(studio_settings) if studio_settings else None
    return create_app(settings, PostgresRepository.from_settings(settings), studio_crm)
