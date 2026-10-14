import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.api.studio import StudioCrm
from tests.test_api import API_SETTINGS, FakeApiRepo
from tests.test_studio_api import SETTINGS, ATTENDANCE

BOOKING = {"personId": ATTENDANCE["personId"], "membershipId": ATTENDANCE["membershipId"], "classSessionId": "00000000-0000-4000-8000-000000000003", "idempotencyKey": "calendar-book"}
CANCELLATION = {"bookingId": "00000000-0000-4000-8000-000000000004", "cancelledAt": "2026-01-01T09:00:00Z", "idempotencyKey": "calendar-cancel"}


@pytest.fixture
def calendar_api():
    requests = []
    def handle(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer server-api-key"
        if request.url.path == "/rest/studioEvents":
            return httpx.Response(200, json={"data": {"studioEvents": [{"id": "event", "eventType": "BOOKING_CREATED"}]}, "pageInfo": {"hasNextPage": False}})
        assert request.url.path in {"/s/studio/bookings/create", "/s/studio/bookings/cancel"}
        return httpx.Response(200, json={"success": True, "duplicate": False})
    studio = StudioCrm(SETTINGS, httpx.Client(transport=httpx.MockTransport(handle)))
    with TestClient(create_app(API_SETTINGS, FakeApiRepo(), studio)) as browser:
        token = browser.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).json()["access_token"]
        yield browser, requests, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("path,body", [("create", BOOKING), ("cancel", CANCELLATION)])
def test_calendar_actions_use_domain_commands_and_stable_keys(calendar_api, path, body):
    browser, requests, headers = calendar_api
    assert browser.post(f"/api/v1/studio/bookings/{path}", json=body).status_code == 401
    assert browser.post(f"/api/v1/studio/bookings/{path}", json=body, headers=headers).status_code == 200
    assert requests[-1].url.path == f"/s/studio/bookings/{path}"
    assert json.loads(requests[-1].content)["idempotencyKey"] == body["idempotencyKey"]
    assert not any(request.url.path.startswith("/rest/studioBookings") for request in requests)


def test_calendar_event_read_and_input_validation(calendar_api):
    browser, requests, headers = calendar_api
    assert browser.get("/api/v1/studio/records/events", headers=headers).json()["items"][0]["eventType"] == "BOOKING_CREATED"
    count = len(requests)
    assert browser.post("/api/v1/studio/bookings/create", json={**BOOKING, "recordedBy": "user"}, headers=headers).status_code == 422
    assert browser.post("/api/v1/studio/bookings/cancel", json={**CANCELLATION, "cancelledAt": "2026-01-01T09:00:00"}, headers=headers).status_code == 422
    assert len(requests) == count
