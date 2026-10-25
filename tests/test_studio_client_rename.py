from __future__ import annotations

import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.api.studio import StudioCrm
from tests.test_api import API_SETTINGS, FakeApiRepo
from tests.test_studio_api import SETTINGS, ATTENDANCE

PERSON_ID = ATTENDANCE["personId"]
RENAME = {"firstName": "Екатерина", "lastName": "Петрова"}


@pytest.fixture
def rename_app():
    person = {
        "id": PERSON_ID,
        "name": {"firstName": "Катя", "lastName": "Иванова"},
        "phones": {"primaryPhoneNumber": "9210000000"},
        "emails": {"primaryEmail": "kate@example.com"},
        "companyId": ATTENDANCE["membershipId"],
    }
    requests = []
    remote = {"person": person, "response": None, "timeout": False}

    def request(request):
        requests.append(request)
        if request.method == "GET":
            assert request.url.path == f"/rest/people/{PERSON_ID}"
            return httpx.Response(200, json={"data": {"person": person}})
        assert request.method == "PATCH"
        assert request.url.path == f"/rest/people/{PERSON_ID}"
        assert request.headers["authorization"] == "Bearer server-api-key"
        if remote["response"] is not None:
            return remote["response"]
        person.update(json.loads(request.content))
        if remote["timeout"]:
            raise httpx.ReadTimeout("response lost", request=request)
        return httpx.Response(200, json={"data": {"updatePerson": person}})

    studio = StudioCrm(SETTINGS, httpx.Client(transport=httpx.MockTransport(request)))
    with TestClient(create_app(API_SETTINGS, FakeApiRepo(), studio)) as browser:
        token = browser.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"}).json()["access_token"]
        yield browser, remote, requests, {"Authorization": f"Bearer {token}"}


def test_rename_updates_existing_person_and_preserves_identity_and_contacts(rename_app):
    browser, remote, requests, headers = rename_app
    original = copy.deepcopy(remote["person"])
    response = browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json={"firstName": "  Екатерина ", "lastName": " Петрова "}, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"id": PERSON_ID, "name": RENAME}
    assert len(requests) == 1
    assert json.loads(requests[0].content) == {"name": RENAME}
    assert remote["person"] == {**original, "name": RENAME}


def test_rename_can_clear_last_name(rename_app):
    browser, remote, _requests, headers = rename_app
    response = browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json={**RENAME, "lastName": "  "}, headers=headers)
    assert response.status_code == 200
    assert remote["person"]["name"] == {**RENAME, "lastName": ""}


@pytest.mark.parametrize("payload", [
    {}, {"firstName": "Катя"}, {**RENAME, "firstName": "  "},
    {**RENAME, "firstName": "а" * 101}, {**RENAME, "lastName": "а" * 101},
    {**RENAME, "firstName": None}, {**RENAME, "lastName": None},
    {**RENAME, "id": ATTENDANCE["membershipId"]}, {**RENAME, "phone": "123"},
    {**RENAME, "companyId": ATTENDANCE["membershipId"]},
])
def test_rename_rejects_invalid_and_unrelated_fields_before_crm(rename_app, payload):
    browser, _remote, requests, headers = rename_app
    assert browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json=payload, headers=headers).status_code == 422
    assert requests == []


def test_rename_requires_login_and_uuid(rename_app):
    browser, _remote, requests, headers = rename_app
    assert browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json=RENAME).status_code == 401
    assert browser.patch("/api/v1/studio/clients/invalid", json=RENAME, headers=headers).status_code == 422
    assert requests == []


@pytest.mark.parametrize("status", [400, 403, 404, 409, 500])
def test_rename_does_not_report_crm_failure_as_success(rename_app, status):
    browser, remote, requests, headers = rename_app
    remote["response"] = httpx.Response(status, json={"message": "Ошибка CRM"})
    response = browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json=RENAME, headers=headers)
    assert response.status_code == (502 if status in {403, 500} else status)
    assert len(requests) == 1


@pytest.mark.parametrize("body", [
    {}, {"data": None}, {"data": []}, {"data": {"updatePerson": None}},
    {"data": {"updatePerson": {"id": ATTENDANCE["membershipId"], "name": RENAME}}},
    {"data": {"updatePerson": {"id": PERSON_ID, "name": {"firstName": "Катя", "lastName": ""}}}},
])
def test_rename_requires_matching_confirmed_identity_and_name(rename_app, body):
    browser, remote, _requests, headers = rename_app
    remote["response"] = httpx.Response(200, json=body)
    response = browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json=RENAME, headers=headers)
    assert response.status_code == 502
    assert "Обновите список" in response.json()["detail"]


def test_rename_lost_response_can_be_safely_retried(rename_app):
    browser, remote, requests, headers = rename_app
    remote["timeout"] = True
    response = browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json=RENAME, headers=headers)
    assert response.status_code == 502
    assert "Обновите список" in response.json()["detail"]
    assert "ключ" not in response.text
    assert remote["person"]["name"] == RENAME
    assert len(requests) == 1
    remote["timeout"] = False
    assert browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json=RENAME, headers=headers).status_code == 200
    assert remote["person"]["id"] == PERSON_ID


def test_edit_adds_gmail_and_preserves_additional_addresses(rename_app):
    browser, remote, requests, headers = rename_app
    remote["person"]["emails"]["additionalEmails"] = ["other@example.com"]
    original = copy.deepcopy(remote["person"])
    response = browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json={**RENAME, "email": "  katfit.test@gmail.com  "}, headers=headers)
    assert response.status_code == 200
    expected_emails = {"primaryEmail": "katfit.test@gmail.com", "additionalEmails": ["other@example.com"]}
    assert response.json() == {"id": PERSON_ID, "name": RENAME, "emails": expected_emails}
    assert json.loads(requests[-1].content) == {"name": RENAME, "emails": expected_emails}
    assert remote["person"] == {**original, "name": RENAME, "emails": expected_emails}


def test_edit_can_clear_primary_email(rename_app):
    browser, remote, _requests, headers = rename_app
    response = browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json={**RENAME, "email": ""}, headers=headers)
    assert response.status_code == 200
    assert remote["person"]["emails"]["primaryEmail"] == ""


@pytest.mark.parametrize("email", [None, "invalid", "a@@gmail.com", "a b@gmail.com", "a" * 255])
def test_edit_rejects_invalid_email(rename_app, email):
    browser, _remote, requests, headers = rename_app
    assert browser.patch(f"/api/v1/studio/clients/{PERSON_ID}", json={**RENAME, "email": email}, headers=headers).status_code == 422
    assert requests == []
