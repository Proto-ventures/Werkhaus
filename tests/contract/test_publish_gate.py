"""The publish gate, taught the difference between a key and a public key.

A site that talks to its own database carries a credential on purpose. Before
this, the scanner blocked every JWT — which meant a working Supabase-backed
site could never be published, while the keys that actually matter
(sb_secret_, whsec_, nfp_, re_) had no patterns at all.
"""

from __future__ import annotations

import base64
import json

import pytest

from tests.contract.conftest import make_engine
from werkhaus.contract.credentials import CredentialClass, classify
from werkhaus.contract.errors import PublishBlocked
from werkhaus.contract.models import ShareOptions
from werkhaus.share.scanner import jwt_role, scan_text


def supabase_jwt(role: str) -> str:
    def part(payload: dict) -> str:
        raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        return raw.rstrip("=")

    head = part({"alg": "HS256", "typ": "JWT"})
    body = part(
        {
            "iss": "supabase",
            "ref": "abcdefghijklmnopqrst",
            "role": role,
            "iat": 1750000000,
            "exp": 1900000000,
        }
    )
    return f"{head}.{body}.d3jK2mQpX8vLc1nR7tYuA0sEwZbHgFiO9pQrStUv"


ANON = supabase_jwt("anon")
SERVICE_ROLE = supabase_jwt("service_role")

REAL_PAGE = f"""<script>
window.WERKHAUS = {{
  SUPABASE_URL: "https://abcdefghijklmnopqrst.supabase.co",
  SUPABASE_ANON_KEY: "{ANON}",
  STRIPE_PUBLISHABLE_KEY: "pk_test_51QxAbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
}};
</script>
"""


# ------------------------------------------------------------------- the scanner
def test_a_working_supabase_page_can_be_published() -> None:
    """The regression this feature would otherwise have caused. Every page that
    talks to a database carries an anon key, and it is meant to."""
    assert scan_text(REAL_PAGE, path="site/config.js") == []


def test_the_service_role_key_is_the_loudest_finding() -> None:
    """Same shape as the anon key, opposite meaning: it bypasses row-level
    security. In a public file it isn't a leaked credential, it's a public
    database."""
    findings = scan_text(f'const admin = "{SERVICE_ROLE}";', path="site/app.js")
    assert findings
    assert "service key" in findings[0].kind
    assert SERVICE_ROLE not in findings[0].excerpt  # never echoed back


def test_the_role_is_read_from_the_token_not_guessed() -> None:
    assert jwt_role(ANON) == "anon"
    assert jwt_role(SERVICE_ROLE) == "service_role"
    assert jwt_role("not a token") is None


@pytest.mark.parametrize(
    "secret",
    [
        "sb_secret_AbCdEfGhIjKlMnOpQrStUvWx",
        "whsec_AbCdEfGhIjKlMnOpQrStUvWx",
        "nfp_AbCdEfGhIjKlMnOpQrStUvWx01",
        "re_AbCdEfGh_IjKlMnOpQrStUvWxYz01",
        "sbp_AbCdEfGhIjKlMnOpQrStUvWx01",
        "rk_test_51QxAbCdEfGhIjKlMnOpQrStUv",
    ],
)
def test_the_keys_that_matter_are_caught(secret: str) -> None:
    assert scan_text(f'KEY = "{secret}"') != []


def test_classification_fails_closed() -> None:
    assert classify("SUPABASE_ANON_KEY") is CredentialClass.PUBLIC
    assert classify("STRIPE_PUBLISHABLE_KEY") is CredentialClass.PUBLIC
    assert classify("SUPABASE_URL") is CredentialClass.REFERENCE
    # Anything a founder typed by hand, and anything we haven't heard of.
    assert classify("MY_OWN_THING") is CredentialClass.SECRET
    assert classify("SUPABASE_SERVICE_ROLE_KEY") is CredentialClass.SECRET


# --------------------------------------------------------------- through publish
async def _company(tmp_path):
    engine = make_engine(tmp_path)
    await engine.start()
    company = await engine.create_company("A refill service for cleaning products")
    return engine, company


async def test_publish_blocks_on_a_stored_secret_in_a_public_file(tmp_path) -> None:
    """`secret_values` used to be accepted by build_snapshot and never passed —
    so a key with no matching pattern went out with the page."""
    engine, company = await _company(tmp_path)
    try:
        await engine.set_vault(company.id, "PARTNER_TOKEN", "zzz-partner-zzz-1234567")
        runtime = engine._get(company.id)
        assert "zzz-partner-zzz-1234567" in engine._secret_values(runtime)

        shift = runtime.brain.open_shift(number=1, agenda=["write notes"])
        doc = runtime.brain.paths.root / "artifacts" / "notes.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("Use zzz-partner-zzz-1234567 to log in.\n", encoding="utf-8")
        artifact = runtime.brain.record_artifact(
            path="artifacts/notes.md",
            title="Notes",
            summary="",
            role_id="chief",
            shift_id=shift.id,
            kind="doc",
            sources=[],
            confidence="assumption",
        )
        runtime.brain.set_artifact_public(artifact.id, True)

        with pytest.raises(PublishBlocked):
            await engine.publish(company.id, ShareOptions())
    finally:
        await engine.aclose()


async def test_a_public_credential_never_blocks_a_publish(tmp_path) -> None:
    """The other half: a stored anon key is not a reason to refuse."""
    engine, company = await _company(tmp_path)
    try:
        await engine.set_vault(company.id, "SUPABASE_ANON_KEY", ANON)
        runtime = engine._get(company.id)
        assert ANON not in engine._secret_values(runtime)
    finally:
        await engine.aclose()


# ------------------------------------------------------------------ the preview
async def test_the_preview_withholds_a_page_with_a_key_in_it(tmp_path) -> None:
    """The share link was gated; the preview was not, so a key baked into the
    page was live the moment it was written."""
    engine, company = await _company(tmp_path)
    try:
        runtime = engine._get(company.id)
        site = runtime.brain.paths.workspace / "site"
        site.mkdir(parents=True, exist_ok=True)
        (site / "index.html").write_text(REAL_PAGE, encoding="utf-8")

        body, mime = await engine.read_site_file(company.id, "index.html")
        assert b"WERKHAUS" in body, "a legitimate page is served untouched"

        (site / "index.html").write_text(
            f'<script>const k = "{SERVICE_ROLE}";</script>', encoding="utf-8"
        )
        body, mime = await engine.read_site_file(company.id, "index.html")
        assert mime == "text/html"
        assert SERVICE_ROLE.encode() not in body
        assert b"not showing this page" in body
        # and the stop became work
        titles = [t.title for t in runtime.brain.state.tasks.values()]
        assert any("private key" in t for t in titles)
    finally:
        await engine.aclose()
