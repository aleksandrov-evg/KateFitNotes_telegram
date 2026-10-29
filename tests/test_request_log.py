import json
import logging

from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from tests.test_api import API_SETTINGS, FakeApiRepo


def events(caplog):
    return [json.loads(record.message) for record in caplog.records if record.name == "uvicorn.error.request_audit"]


def test_all_request_outcomes_are_correlated_and_secrets_are_omitted(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error.request_audit")
    app = create_app(API_SETTINGS, FakeApiRepo())
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"})
        token = login.json()["access_token"]
        success = client.get("/api/v1/clients?q=PRIVATE_PHONE", headers={"Authorization": f"Bearer {token}"})
        unauthorized = client.get("/api/v1/clients")
        invalid = client.post("/api/v1/auth/login", json={"password": "PRIVATE_PASSWORD"})
        missing = client.get("/PRIVATE_PATH")
    finished = [event for event in events(caplog) if event["phase"] == "finished"]
    assert [event["status_code"] for event in finished] == [200, 200, 401, 422, 404]
    assert finished[0]["actor"] == finished[1]["actor"] == "admin"
    assert finished[2]["actor"] is None
    assert finished[1]["route"] == "/clients"
    assert all(event["completed"] for event in finished)
    for response, event in zip([login, success, unauthorized, invalid, missing], finished):
        assert response.headers["x-request-id"] == event["request_id"]
        assert len([entry for entry in events(caplog) if entry["request_id"] == event["request_id"]]) == 2
    assert "PRIVATE_" not in caplog.text
    assert token not in caplog.text
    assert '"password"' not in caplog.text


def test_unhandled_exception_is_logged_and_propagated(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error.request_audit")
    app = create_app(API_SETTINGS, FakeApiRepo())

    @app.get("/test-failure")
    def fail():
        raise RuntimeError("PRIVATE_UPSTREAM_SECRET")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/test-failure").status_code == 500
    event = events(caplog)[-1]
    assert event["status_code"] == 500
    assert event["error_type"] == "RuntimeError"
    assert event["completed"] is False
    assert "PRIVATE_UPSTREAM_SECRET" not in caplog.text
