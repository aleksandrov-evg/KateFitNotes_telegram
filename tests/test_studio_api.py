from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.api.studio import StudioCrm, StudioSettings, load_studio_settings
from src.Kate_Fit_Notes.settings import ConfigError
from tests.test_api import API_SETTINGS, FakeApiRepo

CRM_BASE = "http://crm-stage.lan"
SETTINGS = StudioSettings(CRM_BASE, "server-api-key")
ATTENDANCE = {
    "personId": "00000000-0000-4000-8000-000000000001",
    "membershipId": "00000000-0000-4000-8000-000000000002",
    "startsAt": "2026-01-01T09:00:00Z",
    "endsAt": "2026-01-01T09:55:00Z",
    "source": "ADMIN", "reason": "Тест", "idempotencyKey": "attendance-1",
}


class FakeCrm:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.command_timeout = False
        self.status_code = 200
        self.body = None

    def request(self, request: httpx.Request):
        self.requests.append(request)
        assert request.url.path == "/s/studio/attendance/record-past"
        assert request.headers["authorization"] == "Bearer server-api-key"
        if self.command_timeout:
            raise httpx.ReadTimeout("timeout", request=request)
        body = json.loads(request.content)
        return httpx.Response(self.status_code, json=self.body or {"success": True, "preview": body["previewOnly"], "visitsAvailable": 8, "visitsAfter": 7})


@pytest.fixture
def connected_app():
    remote = FakeCrm()
    studio = StudioCrm(SETTINGS, httpx.Client(transport=httpx.MockTransport(remote.request)))
    with TestClient(create_app(API_SETTINGS, FakeApiRepo(), studio)) as browser:
        token = browser.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).json()["access_token"]
        yield browser, studio, remote, {"Authorization": f"Bearer {token}"}


def test_status_exposes_no_key_and_needs_no_oauth(connected_app):
    browser, studio, remote, headers = connected_app
    response = browser.get("/api/v1/studio/auth/status", headers=headers)
    assert response.json() == {"configured": True, "auth_mode": "api_key"}
    assert "server-api-key" not in response.text
    assert "server-api-key" not in repr(studio.settings)
    assert remote.requests == []
    assert browser.post("/api/v1/studio/auth/connect", headers=headers).status_code == 404
    assert browser.get("/api/v1/studio/auth/callback").status_code == 404


@pytest.mark.parametrize("extra", [{"recordedBy": "another-user"}, {"actorId": "another-user"}, {"previewOnly": False}, {"apiKey": "browser-key"}])
def test_rejects_browser_credentials_and_actor(connected_app, extra):
    browser, _studio, remote, headers = connected_app
    assert browser.post("/api/v1/studio/attendance/preview", json={**ATTENDANCE, **extra}, headers=headers).status_code == 422
    assert remote.requests == []


def test_preview_and_record_are_server_enforced(connected_app):
    browser, _studio, remote, headers = connected_app
    assert browser.post("/api/v1/studio/attendance/preview", json=ATTENDANCE, headers=headers).status_code == 200
    assert json.loads(remote.requests[-1].content)["previewOnly"] is True
    assert browser.post("/api/v1/studio/attendance/record-past", json=ATTENDANCE, headers=headers).status_code == 200
    assert json.loads(remote.requests[-1].content)["previewOnly"] is False


def test_timeout_does_not_retry_and_preserves_operation_key(connected_app):
    browser, _studio, remote, headers = connected_app
    remote.command_timeout = True
    response = browser.post("/api/v1/studio/attendance/record-past", json=ATTENDANCE, headers=headers)
    assert response.status_code == 502
    assert "Результат неизвестен" in response.json()["detail"]
    assert len(remote.requests) == 1
    remote.command_timeout = False
    assert browser.post("/api/v1/studio/attendance/record-past", json=ATTENDANCE, headers=headers).status_code == 200
    assert all(json.loads(request.content)["idempotencyKey"] == "attendance-1" for request in remote.requests)


@pytest.mark.parametrize("status_code", [401, 403])
def test_rejected_server_key_is_not_katefit_login_failure(connected_app, status_code):
    browser, _studio, remote, headers = connected_app
    remote.status_code = status_code
    response = browser.post("/api/v1/studio/attendance/preview", json=ATTENDANCE, headers=headers)
    assert response.status_code == 502
    assert "API-ключ" in response.json()["detail"]
    assert "server-api-key" not in response.text
    assert len(remote.requests) == 1


def test_domain_conflict_remains_visible(connected_app):
    browser, _studio, remote, headers = connected_app
    remote.status_code = 409
    remote.body = {"success": False, "code": "INSUFFICIENT_BALANCE", "message": "Нет посещений"}
    response = browser.post("/api/v1/studio/attendance/preview", json=ATTENDANCE, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INSUFFICIENT_BALANCE"


def test_requires_katefit_login_and_timezone(connected_app):
    browser, _studio, remote, headers = connected_app
    assert browser.get("/api/v1/studio/auth/status").status_code == 401
    for path in ["preview", "record-past"]:
        assert browser.post(f"/api/v1/studio/attendance/{path}", json=ATTENDANCE).status_code == 401
    assert browser.post("/api/v1/studio/attendance/preview", json={**ATTENDANCE, "startsAt": "2026-01-01T09:00:00"}, headers=headers).status_code == 422
    assert remote.requests == []


def test_disabled_crm_keeps_existing_api():
    with TestClient(create_app(API_SETTINGS, FakeApiRepo())) as browser:
        token = browser.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert browser.get("/api/v1/studio/auth/status", headers=headers).json() == {"configured": False, "auth_mode": "api_key"}
        assert browser.post("/api/v1/studio/attendance/preview", json=ATTENDANCE, headers=headers).status_code == 503
        assert browser.get("/health").status_code == 200


def test_loads_server_key_without_oauth(monkeypatch):
    monkeypatch.setenv("CRM_ENABLED", "1")
    monkeypatch.setenv("CRM_BASE_URL", CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", "server-api-key")
    assert load_studio_settings() == SETTINGS
    monkeypatch.delenv("CRM_API_KEY")
    with pytest.raises(ConfigError):
        load_studio_settings()
    monkeypatch.setenv("CRM_ENABLED", "0")
    assert load_studio_settings() is None


@pytest.mark.parametrize("base_url,key", [
    ("http://crm.example.com", "key"),
    (CRM_BASE + "/wrong-path", "key"),
    ("https://user:password@crm.example.com", "key"),
    (CRM_BASE, ""),
    (CRM_BASE, "key\nvalue"),
])
def test_invalid_settings(base_url, key):
    with pytest.raises(ConfigError):
        StudioSettings(base_url, key)
