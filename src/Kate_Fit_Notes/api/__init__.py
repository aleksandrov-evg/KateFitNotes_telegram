"""HTTP API для сайта: те же сервисы, что у бота."""

from src.Kate_Fit_Notes.api.app import app_from_env, create_app

__all__ = ["create_app", "app_from_env"]
