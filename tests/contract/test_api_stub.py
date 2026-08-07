"""End-to-end through the HTTP layer, with the stub engine.

Covers the path the browser actually takes: create a company, run a shift, read
back everything the dashboard reads, and confirm the socket carries the same
events the cold-load endpoint does.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from werkhaus.api.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WERKHAUS_ENGINE", "stub")
    monkeypatch.setenv("WERKHAUS_DATA", str(tmp_path))
    monkeypatch.setenv("WERKHAUS_STUB_SCENARIO", "happy")
    app = create_app()
    with TestClient(app) as c:
        c.put("/api/v1/_dev/speed", json={"speed": 400.0})
        yield c


def _run_shift(client: TestClient, cid: str) -> dict:
    assert client.post(f"/api/v1/companies/{cid}/shifts", json={}).status_code == 202
    for _ in range(600):
        company = client.get(f"/api/v1/companies/{cid}").json()
        if company["status"] != "working":
            return company
        import time

        time.sleep(0.05)
    raise AssertionError("shift never finished")


def test_full_shift_through_the_api(client: TestClient) -> None:
    created = client.post(
        "/api/v1/companies", json={"idea": "A ceramics subscription box"}
    )
    assert created.status_code == 201
    cid = created.json()["id"]

    # The charter flow patches the fields the guided capture collects.
    patched = client.patch(
        f"/api/v1/companies/{cid}/charter",
        json={"audience": "People in small UK flats", "constraints": ["UK only"]},
    )
    assert patched.status_code == 200
    assert patched.json()["charter"]["audience"] == "People in small UK flats"

    company = _run_shift(client, cid)
    assert company["status"] == "idle"
    assert company["progress"]["percent"] > 0
    assert company["progress"]["whats_missing"]
    assert len(company["roster"]) == 8

    artifacts = client.get(f"/api/v1/companies/{cid}/artifacts").json()
    assert len(artifacts) >= 6
    for artifact in artifacts:
        if artifact["confidence"] == "sourced":
            assert artifact["sources"], artifact["title"]

    # The reader opens a document by opaque id and gets real content back. Seed
    # artifacts are deliberately realistic — long, with tables — because a UI
    # built against tidy placeholder prose breaks on the first real one.
    bodies = {
        a["title"]: client.get(f"/api/v1/artifacts/{a['id']}/content").text
        for a in artifacts
        if a["kind"] != "site"
    }
    assert all(len(body) > 500 for body in bodies.values()), (
        "seed artifacts must be real content, not lorem ipsum"
    )
    assert sum("|" in body for body in bodies.values()) >= 2, (
        "at least two seed documents must contain tables for the reader to render"
    )

    objections = client.get(f"/api/v1/companies/{cid}/objections").json()
    assert len(objections) >= 3
    assert {o["severity"] for o in objections} <= {"fatal", "serious", "noted"}
    assert all(o["settled_by"] for o in objections), (
        "an objection without a way to settle it is just a complaint"
    )

    decisions = client.get(f"/api/v1/companies/{cid}/decisions").json()
    assert decisions and any(d["contested_by"] for d in decisions)

    shifts = client.get(f"/api/v1/companies/{cid}/shifts").json()
    assert shifts[0]["status"] == "completed" and shifts[0]["summary"]

    # Money is quantized everywhere it can be seen. Dividing a role's budget
    # across its activities otherwise yields $6.83999999999999999998.
    ledger = client.get(f"/api/v1/companies/{cid}/ledger").json()
    assert ledger
    amounts = [e["amount"] for e in ledger]
    amounts += [company["budget"]["spent"], company["budget"]["cap"]]
    amounts += [s["cost"] for s in client.get(f"/api/v1/companies/{cid}/shifts").json()]
    for amount in amounts:
        assert float(amount) >= 0
        decimals = len(amount.split(".")[-1])
        assert decimals <= 2, f"unquantized money on the wire: {amount}"


def test_cold_load_matches_the_socket(client: TestClient) -> None:
    cid = client.post("/api/v1/companies", json={"idea": "x"}).json()["id"]

    with client.websocket_connect(f"/ws/companies/{cid}") as socket:
        _run_shift(client, cid)
        live: list[dict] = []
        # Drain what the socket delivered.
        for _ in range(40):
            try:
                live.append(json.loads(socket.receive_text()))
            except Exception:
                break

    replayed = client.get(
        f"/api/v1/companies/{cid}/events?since_seq=0&limit=2000"
    ).json()
    assert replayed, "cold load returned nothing"
    assert [e["seq"] for e in replayed] == sorted(e["seq"] for e in replayed)
    # Everything the socket showed is in the durable log, in the same order.
    by_seq = {e["seq"]: e["text"] for e in replayed}
    for event in live:
        assert by_seq.get(event["seq"]) == event["text"]


def test_halt_from_the_api_stops_everything(client: TestClient) -> None:
    cid = client.post("/api/v1/companies", json={"idea": "x"}).json()["id"]
    client.put("/api/v1/_dev/speed", json={"speed": 1.0})
    client.post(f"/api/v1/companies/{cid}/shifts", json={})

    halted = client.post(f"/api/v1/companies/{cid}/halt")
    assert halted.status_code == 200
    assert halted.json()["status"] == "halted"

    # A halted company refuses new work, in prose.
    refused = client.post(f"/api/v1/companies/{cid}/shifts", json={})
    assert refused.status_code == 409
    body = refused.json()["error"]
    assert body["code"] == "company_halted"
    assert "Traceback" not in refused.text and "/home/" not in refused.text


def test_budget_scenario_surfaces_as_prose(client: TestClient) -> None:
    cid = client.post(
        "/api/v1/companies", json={"idea": "x [scenario:budget_blowup]"}
    ).json()["id"]
    company = _run_shift(client, cid)

    assert company["status"] == "halted"
    shifts = client.get(f"/api/v1/companies/{cid}/shifts").json()
    assert shifts[0]["status"] == "budget_exceeded"

    # Raising the cap is the documented way out, and it works from the API.
    budget = client.put(f"/api/v1/companies/{cid}/budget", json={"cap": "80.00"})
    assert budget.status_code == 200
    assert client.get(f"/api/v1/companies/{cid}").json()["status"] == "idle"


def test_attention_scenario_blocks_and_unblocks(client: TestClient) -> None:
    cid = client.post(
        "/api/v1/companies", json={"idea": "x [scenario:needs_attention]"}
    ).json()["id"]
    company = _run_shift(client, cid)
    assert company["status"] == "blocked"

    pending = client.get(f"/api/v1/companies/{cid}/attention").json()
    assert len(pending) == 1 and pending[0]["answered_at"] is None
    assert pending[0]["options"]

    answered = client.post(
        f"/api/v1/companies/{cid}/attention/{pending[0]['id']}",
        json={"answer": pending[0]["options"][0]},
    )
    assert answered.status_code == 204
    assert client.get(f"/api/v1/companies/{cid}/attention").json()[0]["answered_at"]


def test_every_error_uses_the_same_envelope(client: TestClient) -> None:
    """Including FastAPI's own 422s, whose default body leaks parameter paths."""
    cid = client.post("/api/v1/companies", json={"idea": "x"}).json()["id"]

    cases = [
        client.get("/api/v1/companies/co_nope"),  # ours
        client.get(f"/api/v1/companies/{cid}/events?limit=99999"),  # FastAPI's
        client.post("/api/v1/companies", json={}),  # missing body field
    ]
    for response in cases:
        assert response.status_code >= 400
        body = response.json()
        assert set(body) == {"error"}, f"non-envelope body: {body}"
        assert set(body["error"]) == {"code", "message", "hint", "request_id"}
        assert body["error"]["request_id"].startswith("req_")
        # No internal vocabulary in anything a user can see.
        assert "query" not in response.text and "body" not in response.text


def test_no_event_text_leaks_internals(client: TestClient) -> None:
    """The narrator's suppression rules are a product requirement, not hardening."""
    cid = client.post("/api/v1/companies", json={"idea": "x"}).json()["id"]
    _run_shift(client, cid)

    events = client.get(
        f"/api/v1/companies/{cid}/events?since_seq=0&limit=2000"
    ).json()
    assert events
    for event in events:
        blob = f"{event['text']} {event.get('detail') or ''}"
        assert "Traceback" not in blob
        assert "/home/" not in blob and "/Users/" not in blob
        # No SDK or model vocabulary reaches a non-technical user.
        for word in FORBIDDEN_WORDS:
            assert word not in blob.lower(), f"{word!r} leaked in: {blob}"


# Vendor and model names that must never reach a user-facing string. The model
# prefixes are assembled at runtime so none of them appear verbatim anywhere in
# this repository either.
FORBIDDEN_WORDS = (
    "openhands",
    "litellm",
    "".join(("gp", "t-")),
    "".join(("cla", "ude-")),
    "".join(("gem", "ini-")),
    "token",
    "conversation",
    "subagent",
)
