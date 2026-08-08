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

from tests.contract.conftest import make_engine
from werkhaus.api.app import create_app

SECRET = "sq_live_9f8e7d6c5b4a39281706fedcba543210"


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """The HTTP layer over the real engine, thinking with a scripted model."""
    monkeypatch.setenv("WERKHAUS_DATA", str(tmp_path))
    app = create_app(engine=make_engine(tmp_path))
    with TestClient(app) as c:
        c.tmp_path = tmp_path  # type: ignore[attr-defined]
        yield c


def _company(client: TestClient) -> str:
    return client.post(
        "/api/v1/companies", json={"idea": "A booking tool for mobile dog groomers"}
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
def _put_site(client: TestClient, cid: str) -> None:
    """A built site on disk.

    Written here rather than produced by a shift: these tests are about the
    serving path — containment, mime types, traversal — and Kit, who builds
    sites for real, arrives with the rest of the roster.
    """
    site = client.tmp_path / cid / "workspace" / "site"  # type: ignore[attr-defined]
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text(
        "<!doctype html>\n<html><body><h1>Join the waitlist</h1></body></html>\n",
        encoding="utf-8",
    )
    (site / "styles.css").write_text("body{font-family:system-ui}\n", encoding="utf-8")


def test_files_are_real_and_workspace_only(client: TestClient) -> None:
    cid = _company(client)
    _run_shift(client, cid)
    _put_site(client, cid)

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
    _put_site(client, cid)

    page = client.get(f"/api/v1/companies/{cid}/site/")
    assert page.status_code == 200
    assert "waitlist" in page.text.lower()
    assert client.get(f"/api/v1/companies/{cid}/site/styles.css").status_code == 200

    # Encoded so the client can't normalise it away: the handler receives
    # "../_state/log.jsonl" and the containment check refuses it.
    traversal = client.get(
        f"/api/v1/companies/{cid}/site/..%2F_state%2Flog.jsonl"
    )
    assert traversal.status_code == 404
    assert "shift" not in traversal.text
