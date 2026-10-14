import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.api.studio import StudioCrm
from tests.studio_event_fake import FakeStudioEvents
from tests.test_api import API_SETTINGS, FakeApiRepo
from tests.test_studio_api import ATTENDANCE, SETTINGS
from tests.test_studio_calendar_api import BOOKING, CANCELLATION, SESSION
from tests.test_studio_records import CLIENT, PAYMENT, records_app


@pytest.mark.parametrize("mode", ["fail_success_write", "lose_success_response"])
def test_client_success_requires_audit_and_same_key_recovers(records_app, mode):
    browser, remote, headers = records_app
    setattr(remote.audit, mode, True)
    assert browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers).status_code == 502
    assert len(remote.people) == 1
    repeated = browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["duplicate"] is True
    assert browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers).status_code == 200
    successes = [event for event in remote.audit.events.values() if event["outcome"] == "SUCCESS"]
    assert len(successes) == 1
    assert successes[0]["eventType"] == "CLIENT_CREATED"
    assert json.loads(successes[0]["details"]) == {"personId": CLIENT["clientId"], "source": "KATEFIT_UI", "operator": "admin"}
    assert len([request for request in remote.requests if request.method == "POST" and request.url.path == "/rest/people"]) == 1


@pytest.mark.parametrize("path,body", [
    ("clients", CLIENT), ("package-payments/confirm", PAYMENT),
    ("attendance/record-past", ATTENDANCE), ("sessions/create", SESSION),
    ("bookings/create", BOOKING), ("bookings/cancel", CANCELLATION),
])
def test_all_mutating_routes_log_rejections_once(monkeypatch, path, body):
    audit = FakeStudioEvents()

    def rejected(*_arguments, **_keywords):
        raise HTTPException(409, {"code": "DOMAIN_REJECTED", "message": "Операция отклонена"})

    monkeypatch.setattr(StudioCrm, "command", rejected)
    monkeypatch.setattr(StudioCrm, "create_person", rejected)
    studio = StudioCrm(SETTINGS, httpx.Client(transport=httpx.MockTransport(audit.handle)))
    with TestClient(create_app(API_SETTINGS, FakeApiRepo(), studio)) as browser:
        token = browser.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        for _attempt in range(2):
            response = browser.post("/api/v1/studio/" + path, json=body, headers=headers)
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "DOMAIN_REJECTED"
        assert len(audit.events) == 1
        event = next(iter(audit.events.values()))
        assert event["eventType"] == "OPERATION_FAILED"
        details = json.loads(event["details"])
        assert details["operator"] == "admin"
        assert details["execution"] == "REJECTED"


def test_unknown_response_is_not_reported_as_rollback(records_app):
    browser, remote, headers = records_app
    remote.timeout = True
    assert browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers).status_code == 502
    assert len(remote.people) == 1
    event = next(iter(remote.audit.events.values()))
    assert json.loads(event["details"])["execution"] == "UNKNOWN"
    remote.timeout = False
    remote.audit.unavailable = True
    response = browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "AUDIT_UNCONFIRMED"
    assert "журнала также не подтверждена" in response.json()["detail"]["message"]
    remote.audit.unavailable = False
    assert browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers).json()["duplicate"] is True
    assert len(remote.people) == 1


def test_conflicting_client_event_never_returns_success(records_app):
    browser, remote, headers = records_app
    assert browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers).status_code == 200
    remote.audit.events[CLIENT["clientId"]]["details"] = "{}"
    assert browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers).status_code == 409
    assert len(remote.people) == 1
