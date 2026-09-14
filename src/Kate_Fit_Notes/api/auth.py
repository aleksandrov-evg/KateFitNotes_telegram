"""JWT-логин одного админа из env. Без таблицы пользователей."""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.Kate_Fit_Notes.api.deps import get_settings
from src.Kate_Fit_Notes.api.schemas import LoginRequest, TokenResponse
from src.Kate_Fit_Notes.settings import Settings

JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=24)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def create_access_token(username: str, secret: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> str:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="не авторизован",
        ) from exc
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="не авторизован",
        )
    return str(subject)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    user_ok = hmac.compare_digest(body.username, settings.api_user or "")
    password_ok = hmac.compare_digest(body.password, settings.api_password or "")
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="неверный логин или пароль",
        )
    token = create_access_token(body.username, settings.api_jwt_secret or "")
    return TokenResponse(access_token=token)


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="не авторизован",
        )
    return decode_access_token(credentials.credentials, settings.api_jwt_secret or "")
