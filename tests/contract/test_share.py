"""The publish gate.

A share link is the one place where a bug becomes a public data breach, so the
rule is: never serve the live directory, allowlist rather than filter, and fail
closed on anything that smells like a secret.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.contract.conftest import make_engine, prepare_workspace, wait_idle
from werkhaus.contract.errors import PublishBlocked
from werkhaus.contract.models import Progress, ShareOptions
from werkhaus.share.scanner import scan_text, scan_tree
from werkhaus.share.snapshot import build_snapshot

FAST = 400.0

SECRETS = [
    "sk-abcdef0123456789abcdef0123456789",
    "sk-ant-api03-AAAAbbbbCCCCddddEEEEffff1111",
    "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",
    "AKIAIOSFODNN7EXAMPLE",
    "xoxb-1234567890-abcdefghijkl",
    "postgres://admin:hunter2@db.internal:5432/app",
    "-----BEGIN RSA PRIVATE KEY-----",
    "api_key = 8f4b2c9e1a7d5063f8b2",
    "/home/lummy/.ssh/id_rsa",
]

INNOCENT = [
    "The £29 price is defended against competitors, not customers.",
    "See https://claycollective.uk/subscribe for their pricing page.",
    "Contribution is about £9.85 per box if three assumptions hold.",
    "Read artifacts/market-research.md for the competitor table.",
    "risk-assessment.md covers the breakage question",
    "a-fairly-long-kebab-case-identifier-here",
]


@pytest.mark.parametrize("secret", SECRETS)
def test_scanner_catches_real_secrets(secret: str) -> None:
    assert scan_text(f"the value is {secret} okay"), f"missed: {secret}"


@pytest.mark.parametrize("line", INNOCENT)
def test_scanner_leaves_ordinary_prose_alone(line: str) -> None:
    """False positives block publishing, so they are not free either."""
    assert not scan_text(line), f"false positive on: {line}"


def test_findings_never_echo_the_secret() -> None:
    secret = "sk-abcdef0123456789abcdef0123456789"
    findings = scan_text(f"key={secret}")
    assert findings
    for finding in findings:
        assert secret not in finding.excerpt
        assert secret not in str(finding)


def test_publish_is_blocked_when_a_key_leaks(tmp_path: Path) -> None:
    company = tmp_path / "co_x"
    (company / "artifacts").mkdir(parents=True)
    (company / "artifacts" / "notes.md").write_text(
        "Deploy with sk-abcdef0123456789abcdef0123456789\n"
    )

    from datetime import UTC, datetime

    from werkhaus.contract.models import Artifact

    artifact = Artifact(
        id="ar_1", company_id="co_x", kind="doc", title="Notes", summary="s",
        path="artifacts/notes.md", produced_by="engineer",
        produced_in_shift="co_x/0001", confidence="assumption", sources=[],
        public=True, updated_at=datetime.now(UTC),
    )
    with pytest.raises(PublishBlocked):
        build_snapshot(
            company_root=company, share_root=tmp_path / "_share", token="tok",
            company_name="X", one_liner="y",
            progress=Progress(percent=1, headline="h"), roster=[], shifts=[],
            artifacts=[artifact], decisions=[], objections=[],
        )
    # Fail closed *and* leave nothing behind that a route could stumble onto.
    assert not (tmp_path / "_share" / "tok").exists()


async def test_a_snapshot_only_contains_what_was_opted_in(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    await engine.start()
    company = await engine.create_company("A booking tool for dog groomers")
    prepare_workspace(tmp_path, company.id)
    await engine.start_shift(company.id)
    await wait_idle(engine, company.id)

    brain = engine._companies[company.id].brain
    # Private notes and engine state exist and must never be enumerated.
    (brain.paths.notes / "researcher").mkdir(parents=True, exist_ok=True)
    (brain.paths.notes / "researcher" / "scratch.md").write_text(
        "internal only: sk-abcdef0123456789abcdef0123456789\n"
    )

    artifacts = await engine.list_artifacts(company.id)
    brain.set_artifact_public(artifacts[0].id, True)

    link = await engine.publish(company.id, ShareOptions())
    assert link.scanned_clean_at is not None, "a clean scan must mark the link servable"

    snapshot_root = tmp_path / "_share" / link.token
    files = {p.name for p in snapshot_root.rglob("*") if p.is_file()}
    assert "manifest.json" in files
    assert "scratch.md" not in files, "private notes reached the snapshot"
    assert not (snapshot_root / "_state").exists()
    assert not (snapshot_root / "workspace").exists()
    # And the snapshot itself is clean, by the same scanner that gated it.
    assert not scan_tree(snapshot_root)

    # Only the opted-in artifact travelled.
    served = await engine.get_public_snapshot(link.token)
    assert len(served.artifacts) == 1
    await engine.aclose()


async def test_unpublished_links_stop_serving(tmp_path: Path) -> None:
    from werkhaus.contract.errors import NotFound

    engine = make_engine(tmp_path)
    await engine.start()
    company = await engine.create_company("x")
    link = await engine.publish(company.id, ShareOptions())
    assert await engine.get_public_snapshot(link.token)

    await engine.unpublish(company.id)
    with pytest.raises(NotFound):
        await engine.get_public_snapshot(link.token)
    assert not (tmp_path / "_share" / link.token).exists()
    await engine.aclose()
