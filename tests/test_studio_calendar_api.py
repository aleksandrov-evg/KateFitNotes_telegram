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
SESSION = {"name": "Реформер", "sessionFormat": "GROUP_REFORMER", "startsAt": "2026-10-15T10:00:00+03:00", "durationMinutes": 55, "capacity": 4, "status": "PLANNED", "idempotencyKey": "session-create"}


@pytest.fixture
def calendar_api():
    requests = []
    def handle(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer server-api-key"
        if request.url.path == "/rest/studioEvents":
            return httpx.Response(200, json={"data": {"studioEvents": [{"id": "event", "eventType": "BOOKING_CREATED"}]}, "pageInfo": {"hasNextPage": False}})
        assert request.url.path in {"/s/studio/bookings/create", "/s/studio/bookings/cancel", "/s/studio/bookings/cancel-pay-as-you-go", "/s/studio/sessions/create", "/s/studio/sessions/payment"}
        return httpx.Response(200, json={"success": True, "duplicate": False})
    studio = StudioCrm(SETTINGS, httpx.Client(transport=httpx.MockTransport(handle)))
    with TestClient(create_app(API_SETTINGS, FakeApiRepo(), studio)) as browser:
        token = browser.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).json()["access_token"]
        yield browser, requests, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("path,body", [("create", BOOKING), ("cancel", CANCELLATION), ("cancel-pay-as-you-go", CANCELLATION)])
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


def test_session_creation_uses_authenticated_command(calendar_api):
    browser, requests, headers = calendar_api
    assert browser.post("/api/v1/studio/sessions/create", json=SESSION).status_code == 401
    assert browser.post("/api/v1/studio/sessions/create", json=SESSION, headers=headers).status_code == 200
    assert requests[-1].url.path == "/s/studio/sessions/create"
    assert json.loads(requests[-1].content)["idempotencyKey"] == SESSION["idempotencyKey"]
    assert not any(request.url.path == "/rest/classSessions" for request in requests)
    body = {**SESSION, "participants": [{"personId": BOOKING["personId"], "membershipId": BOOKING["membershipId"]}]}
    assert browser.post("/api/v1/studio/sessions/create", json=body, headers=headers).status_code == 200
    assert json.loads(requests[-1].content)["participants"] == body["participants"]
    assert browser.post("/api/v1/studio/sessions/create", json={**body, "participants": [{"personId": "bad", "membershipId": BOOKING["membershipId"]}]}, headers=headers).status_code == 422


@pytest.mark.parametrize("change", [{"startsAt": "2026-10-15T10:00:00"}, {"durationMinutes": 0}, {"durationMinutes": 1.5}, {"capacity": 101}, {"status": "CANCELLED"}, {"recordedBy": "operator"}])
def test_session_body_validation_before_crm(calendar_api, change):
    browser, requests, headers = calendar_api
    assert browser.post("/api/v1/studio/sessions/create", json={**SESSION, **change}, headers=headers).status_code == 422
    assert requests == []


def test_inline_session_payment_and_mixed_participants(calendar_api):
    browser, requests, headers = calendar_api
    payment = {key: value for key, value in SESSION.items() if key in {"sessionFormat", "startsAt", "durationMinutes", "status", "idempotencyKey"}}
    payment.update(personId=BOOKING["personId"], productId="00000000-0000-4000-8000-000000000005", paymentMethod="SBP")
    assert browser.post("/api/v1/studio/sessions/payment", json=payment).status_code == 401
    assert browser.post("/api/v1/studio/sessions/payment", json=payment, headers=headers).status_code == 200
    assert requests[-1].url.path == "/s/studio/sessions/payment"
    assert json.loads(requests[-1].content)["startsAt"].endswith("+03:00")
    participants = [{"personId": BOOKING["personId"], "membershipId": BOOKING["membershipId"]},
                    {"personId": "00000000-0000-4000-8000-000000000006", "productId": payment["productId"], "paymentId": "00000000-0000-4000-8000-000000000007"}]
    assert browser.post("/api/v1/studio/sessions/create", json={**SESSION, "participants": participants}, headers=headers).status_code == 200
    assert json.loads(requests[-1].content)["participants"] == participants
    for change in [{"startsAt": "2026-10-15T10:00:00"}, {"status": "CONFIRMED"}, {"amount": 1}]:
        assert browser.post("/api/v1/studio/sessions/payment", json={**payment, **change}, headers=headers).status_code == 422
    assert browser.post("/api/v1/studio/sessions/create", json={**SESSION, "participants": [{**participants[0], "paymentId": participants[1]["paymentId"]}]}, headers=headers).status_code == 422
