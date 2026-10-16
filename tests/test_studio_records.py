from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.api.studio import StudioCrm
from tests.test_api import API_SETTINGS, FakeApiRepo
from tests.test_studio_api import SETTINGS, ATTENDANCE
from tests.studio_event_fake import FakeStudioEvents

CLIENT = {"clientId": ATTENDANCE["personId"], "firstName": "Катя", "lastName": "Иванова", "phone": "+7 (921) 000-00-00", "email": "kate@example.com"}
PAYMENT = {"personId": ATTENDANCE["personId"], "productId": ATTENDANCE["membershipId"], "paidAt": "2026-01-01T09:00:00Z", "amount": 10000, "paymentMethod": "SBP", "idempotencyKey": "payment-1"}


class FakeRecordsCrm:
    def __init__(self):
        self.requests = []
        self.people = {}
        self.invalid_cursor = False
        self.timeout = False
        self.reject_person = False
        self.audit = FakeStudioEvents()

    def request(self, request):
        self.requests.append(request)
        assert request.headers["authorization"] == "Bearer server-api-key"
        path = request.url.path
        audit_response = self.audit.handle(request)
        if audit_response is not None:
            return audit_response
        if request.method == "GET" and path == "/rest/people":
            if request.url.params.get("filter"):
                phone = request.url.params["filter"].split(":")[-1]
                return httpx.Response(200, json={"data": {"people": [person for person in self.people.values() if person["phones"]["primaryPhoneNumber"] == phone]}})
            if request.url.params.get("starting_after"):
                return httpx.Response(200, json={"data": {"people": [{"id": "two"}]}, "pageInfo": {"hasNextPage": False}})
            return httpx.Response(200, json={"data": {"people": [{"id": "one"}]}, "pageInfo": {"hasNextPage": True, "endCursor": None if self.invalid_cursor else "cursor-1"}})
        if request.method == "GET" and path.startswith("/rest/people/"):
            person = self.people.get(path.rsplit("/", 1)[1])
            return httpx.Response(200, json={"data": {"person": person}}) if person else httpx.Response(404, json={"message": "Not found"})
        if request.method == "POST" and path == "/rest/people":
            body = json.loads(request.content)
            if self.reject_person:
                return httpx.Response(400, json={"code": "CRM_ERROR", "message": "A duplicate entry was detected"})
            body["id"] = "created-" + str(len(self.people) + 1)
            self.people[body["id"]] = body
            if self.timeout:
                raise httpx.ReadTimeout("timeout", request=request)
            return httpx.Response(201, json={"data": {"createPerson": body}})
        if path == "/s/studio/package-payments/confirm":
            return httpx.Response(200, json={"success": True, "membershipId": "package", "visitsAvailable": 8})
        raise AssertionError(f"Unexpected route: {request.method} {path}")


@pytest.fixture
def records_app():
    remote = FakeRecordsCrm()
    studio = StudioCrm(SETTINGS, httpx.Client(transport=httpx.MockTransport(remote.request)))
    with TestClient(create_app(API_SETTINGS, FakeApiRepo(), studio)) as browser:
        token = browser.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).json()["access_token"]
        yield browser, remote, {"Authorization": f"Bearer {token}"}


def test_cursor_and_resource_allowlist(records_app):
    browser, remote, headers = records_app
    first = browser.get("/api/v1/studio/records/clients", headers=headers)
    assert first.json() == {"items": [{"id": "one"}], "next_cursor": "cursor-1"}
    second = browser.get("/api/v1/studio/records/clients?cursor=cursor-1", headers=headers)
    assert second.json() == {"items": [{"id": "two"}], "next_cursor": None}
    assert remote.requests[-1].url.params["starting_after"] == "cursor-1"
    assert browser.get("/api/v1/studio/records/apiKeys", headers=headers).status_code == 422
    assert browser.get("/api/v1/studio/records/clients").status_code == 401
    remote.invalid_cursor = True
    assert browser.get("/api/v1/studio/records/clients", headers=headers).status_code == 502


def test_client_creation_normalizes_contact_and_recovers_lost_response(records_app):
    browser, remote, headers = records_app
    remote.timeout = True
    assert browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers).status_code == 502
    remote.timeout = False
    repeated = browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers)
    assert repeated.json() == {"id": "created-1", "duplicate": True}
    creates = [request for request in remote.requests if request.method == "POST" and request.url.path == "/rest/people"]
    assert len(creates) == 1
    assert "id" not in json.loads(creates[0].content)
    person = remote.people["created-1"]
    assert person["name"] == {"firstName": "Катя", "lastName": "Иванова"}
    assert person["phones"]["primaryPhoneNumber"] == "9210000000"
    assert person["phones"]["primaryPhoneCallingCode"] == "+7"
    assert browser.post("/api/v1/studio/clients", json={**CLIENT, "firstName": "Другое имя"}, headers=headers).status_code == 409
    assert browser.post("/api/v1/studio/clients", json={**CLIENT, "clientId": ATTENDANCE["membershipId"]}, headers=headers).json() == {"id": "created-1", "duplicate": True}


def test_client_without_email_does_not_send_empty_email_to_crm(records_app):
    browser, remote, headers = records_app
    payload = {**CLIENT, "clientId": ATTENDANCE["membershipId"], "email": ""}

    response = browser.post("/api/v1/studio/clients", json=payload, headers=headers)

    assert response.status_code == 200
    assert "emails" not in remote.people[response.json()["id"]]


def test_client_rejection_returns_exact_crm_payload(records_app):
    browser, remote, headers = records_app
    remote.reject_person = True

    response = browser.post("/api/v1/studio/clients", json=CLIENT, headers=headers)

    assert response.status_code == 400
    payload = response.json()["detail"]["crmPayload"]
    assert payload == {
        "name": {"firstName": "Катя", "lastName": "Иванова"},
        "phones": {"primaryPhoneNumber": "9210000000", "primaryPhoneCountryCode": "RU", "primaryPhoneCallingCode": "+7"},
        "emails": {"primaryEmail": "kate@example.com"},
    }


@pytest.mark.parametrize("extra", [{"phone": "123"}, {"email": "bad"}, {"recordedBy": "user"}, {"apiKey": "browser-secret"}])
def test_client_validation_before_crm(records_app, extra):
    browser, remote, headers = records_app
    assert browser.post("/api/v1/studio/clients", json={**CLIENT, **extra}, headers=headers).status_code == 422
    assert remote.requests == []


def test_package_created_only_through_payment_command(records_app):
    browser, remote, headers = records_app
    assert browser.post("/api/v1/studio/package-payments/confirm", json=PAYMENT).status_code == 401
    result = browser.post("/api/v1/studio/package-payments/confirm", json=PAYMENT, headers=headers)
    assert result.status_code == 200
    assert result.json()["membershipId"] == "package"
    assert remote.requests[-1].url.path == "/s/studio/package-payments/confirm"
    body = json.loads(remote.requests[-1].content)
    assert body["idempotencyKey"] == PAYMENT["idempotencyKey"]
    assert body["amount"] == 10000
    assert not any(request.url.path == "/rest/studioMemberships" for request in remote.requests)
    assert browser.post("/api/v1/studio/package-payments/confirm", json={**PAYMENT, "paidAt": "2026-01-01T09:00:00"}, headers=headers).status_code == 422
    assert browser.post("/api/v1/studio/package-payments/confirm", json={**PAYMENT, "amount": -1}, headers=headers).status_code == 422
