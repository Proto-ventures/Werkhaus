"""The vault, the workspace files, and the served site.

Three properties matter and all three are about trust:

* A vault value goes in once and never comes back out — not in the vault list,
  not in events, not anywhere.
* The file endpoints can only see ``workspace/``. ``_state`` (the log, the
  vault) is unreachable by construction, not by filtering.
* The site the Website tab iframes is real files Kit wrote, at a real URL.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from werkhaus.api.app import create_app

SECRET = "sq_live_9f8e7d6c5b4a39281706fedcba543210"


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WERKHAUS_ENGINE", "stub")
    monkeypatch.setenv("WERKHAUS_DATA", str(tmp_path))
    monkeypatch.setenv("WERKHAUS_STUB_SCENARIO", "happy")
    app = create_app()
    with TestClient(app) as c:
        c.put("/api/v1/_dev/speed", json={"speed": 400.0})
        yield c


def _company(client: TestClient) -> str:
    return client.post(
        "/api/v1/companies", json={"idea": "A ceramics subscription box"}
    ).json()["id"]


def _run_shift(client: TestClient, cid: str) -> None:
    assert client.post(f"/api/v1/companies/{cid}/shifts", json={}).status_code == 202
    for _ in range(600):
        if client.get(f"/api/v1/companies/{cid}").json()["status"] != "working":
            return
        time.sleep(0.05)
    raise AssertionError("shift never finished")


# ----------------------------------------------------------------------- vault
def test_vault_value_never_comes_back(client: TestClient, tmp_path) -> None:
    cid = _company(client)

    put = client.put(
        f"/api/v1/companies/{cid}/vault/STRIPE_KEY", json={"value": SECRET}
    )
    assert put.status_code == 200
    assert SECRET not in put.text

    listed = client.get(f"/api/v1/companies/{cid}/vault").json()
    assert [item["name"] for item in listed] == ["STRIPE_KEY"]
    assert SECRET not in json.dumps(listed)
    # The hint is enough to tell keys apart, not enough to use one.
    assert listed[0]["hint"].endswith(SECRET[-2:])

    # Nothing else echoes it either: company, events, files.
    for path in (
        f"/api/v1/companies/{cid}",
        f"/api/v1/companies/{cid}/events?since_seq=0&limit=2000",
        f"/api/v1/companies/{cid}/files",
    ):
        assert SECRET not in client.get(path).text, path

    # And it never lands in the event log on disk.
    log = next(tmp_path.glob("co_*/_state/log.jsonl"))
    assert SECRET not in log.read_text(encoding="utf-8")

    assert (
        client.delete(f"/api/v1/companies/{cid}/vault/STRIPE_KEY").status_code == 204
    )
    assert client.get(f"/api/v1/companies/{cid}/vault").json() == []


def test_vault_rejects_a_hostile_name(client: TestClient) -> None:
    cid = _company(client)
    # A path-shaped name never reaches the handler at all.
    routed = client.put(
        f"/api/v1/companies/{cid}/vault/..%2F..%2Fetc", json={"value": SECRET}
    )
    assert routed.status_code in (404, 405, 422)
    assert SECRET not in routed.text

    # A merely malformed one is refused by the validator, in prose.
    bad = client.put(
        f"/api/v1/companies/{cid}/vault/9 bad name", json={"value": SECRET}
    )
    assert bad.status_code == 422
    assert SECRET not in bad.text
    assert bad.json()["error"]["code"] == "invalid_request"


# ------------------------------------------------------------------- workspace
def test_files_are_real_and_workspace_only(client: TestClient) -> None:
    cid = _company(client)
    _run_shift(client, cid)

    files = client.get(f"/api/v1/companies/{cid}/files").json()
    paths = {f["path"] for f in files}
    assert "site/index.html" in paths
    # Nothing outside workspace/ is ever enumerated.
    assert not any(p.startswith(("_state", "..", "/")) for p in paths)

    content = client.get(
        f"/api/v1/companies/{cid}/files/content", params={"path": "site/index.html"}
    )
    assert content.status_code == 200
    assert "<!doctype html>" in content.text

    for hostile in ("../_state/log.jsonl", "../../secrets", "/etc/passwd"):
        response = client.get(
            f"/api/v1/companies/{cid}/files/content", params={"path": hostile}
        )
        assert response.status_code == 404, hostile


# ------------------------------------------------------------------------ site
def test_site_is_served_for_real(client: TestClient) -> None:
    cid = _company(client)
    _run_shift(client, cid)

    page = client.get(f"/api/v1/companies/{cid}/site/")
    assert page.status_code == 200
    assert "waitlist" in page.text.lower()
    assert client.get(f"/api/v1/companies/{cid}/site/styles.css").status_code == 200

    # The site artifact points at this URL, so the dashboard needs no
    # special-casing to find it.
    artifacts = client.get(f"/api/v1/companies/{cid}/artifacts").json()
    site = next(a for a in artifacts if a["kind"] == "site")
    assert site["preview_url"] == f"/api/v1/companies/{cid}/site/"

    # Encoded so the client can't normalise it away: the handler receives
    # "../_state/log.jsonl" and the containment check refuses it.
    traversal = client.get(
        f"/api/v1/companies/{cid}/site/..%2F_state%2Flog.jsonl"
    )
    assert traversal.status_code == 404
    assert "shift" not in traversal.text
