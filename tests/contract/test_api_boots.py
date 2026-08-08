"""M0 smoke: the API boots, the contract serializes, the socket heartbeats."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from werkhaus.api.app import create_app
from werkhaus.contract.events import ShiftEventKind


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    # No model configured: the API still serves, and says why it cannot work.
    monkeypatch.delenv("WERKHAUS_MODEL", raising=False)
    with TestClient(create_app()) as c:
        yield c


def test_healthz(client: TestClient) -> None:
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["engine"] == "NullEngine"


def test_list_companies_is_empty(client: TestClient) -> None:
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    assert response.json() == []


def test_missing_company_returns_prose_not_a_traceback(client: TestClient) -> None:
    response = client.get("/api/v1/companies/co_nope")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "company_not_found"
    assert error["message"] == "That company doesn't exist."
    assert error["request_id"].startswith("req_")
    # The whole point: nothing internal leaks to a non-technical user.
    assert "Traceback" not in response.text
    assert "/home/" not in response.text


def test_openapi_schema_exposes_the_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "Company" in schema["components"]["schemas"]
    assert "ShiftEvent" in schema["components"]["schemas"]
    assert "/api/v1/companies/{cid}/halt" in schema["paths"]


def test_socket_heartbeats(client: TestClient) -> None:
    with client.websocket_connect("/ws/companies/co_demo") as socket:
        event = json.loads(socket.receive_text())
    assert event["kind"] == ShiftEventKind.HEARTBEAT
    assert event["seq"] == 1
    assert event["company_id"] == "co_demo"
