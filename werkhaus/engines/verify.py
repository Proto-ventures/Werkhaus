"""Ask the provider whether the key works, before storing it.

A credential that fails halfway through a shift costs a whole shift, and on the
free plan a founder has three. So every key is exercised against the real API at
the moment it is pasted, while the person who can fix it is still looking at the
screen — and nothing is written until it passes.

The probes are deliberately the cheapest read each provider offers. We are
answering one question ("does this work, and is it allowed to do what we need"),
not inspecting anyone's account.

No ``openhands.*`` imports: this must stay importable without the SDK.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

TIMEOUT = 8.0


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    message: str
    """User prose either way. Never a status code, never a response body."""

    hint: str | None = None
    facts: dict[str, str] = field(default_factory=dict)
    """Values discovered during the check that are worth keeping — a project
    ref when the account has exactly one, say."""

    scope_note: str | None = None
    """What this key can and cannot do, in the founder's terms."""


class Verifier(Protocol):
    async def check(self, provider: str, values: dict[str, str]) -> VerifyResult: ...


class NullVerifier:
    """Approves everything. For tests, and for nothing else."""

    async def check(self, provider: str, values: dict[str, str]) -> VerifyResult:
        return VerifyResult(True, "Connected.")


class HttpVerifier:
    """The real thing."""

    def __init__(self, timeout: float = TIMEOUT) -> None:
        self.timeout = timeout

    async def check(self, provider: str, values: dict[str, str]) -> VerifyResult:
        method = getattr(self, f"_{provider}", None)
        if method is None:
            # Never claim a connection we did not confirm.
            return VerifyResult(
                False,
                "We can't check this one from here yet.",
                hint="Nothing was saved.",
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                return await method(client, values)
        except httpx.TimeoutException:
            return VerifyResult(
                False,
                "The service didn't answer in time.",
                hint="It may be having a moment. Try again shortly — nothing "
                "was saved.",
            )
        except httpx.HTTPError:
            logger.warning("verification failed for %s", provider, exc_info=True)
            return VerifyResult(
                False,
                "We couldn't reach that service.",
                hint="Check your internet connection. Nothing was saved.",
            )

    # ----------------------------------------------------------------- probes
    async def _supabase(
        self, client: httpx.AsyncClient, values: dict[str, str]
    ) -> VerifyResult:
        token = values.get("SUPABASE_ACCESS_TOKEN", "")
        response = await client.get(
            "https://api.supabase.com/v1/projects",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code in (401, 403):
            return VerifyResult(
                False,
                "Supabase didn't recognise that token.",
                hint="Tokens are shown only once, so a half-copied one is the "
                "usual cause. Generate another and paste the whole value.",
            )
        if response.status_code >= 400:
            return VerifyResult(False, "Supabase turned that token down.")

        facts: dict[str, str] = {}
        note = "The team can create and change your database."
        try:
            projects = response.json()
        except ValueError:
            projects = []
        if isinstance(projects, list) and len(projects) == 1:
            only = projects[0]
            ref = str(only.get("id", ""))
            if ref:
                facts["SUPABASE_PROJECT_REF"] = ref
                facts["SUPABASE_URL"] = f"https://{ref}.supabase.co"
                note = (
                    f"The team will work in your existing project "
                    f"“{only.get('name', ref)}” rather than making a new one."
                )
        return VerifyResult(
            True, "Supabase is connected.", scope_note=note, facts=facts
        )

    async def _netlify(
        self, client: httpx.AsyncClient, values: dict[str, str]
    ) -> VerifyResult:
        token = values.get("NETLIFY_PERSONAL_ACCESS_TOKEN", "")
        response = await client.get(
            "https://api.netlify.com/api/v1/user",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code in (401, 403):
            return VerifyResult(
                False,
                "Netlify didn't recognise that token.",
                hint="Make sure you copied the personal access token, not the "
                "site id from the same page.",
            )
        if response.status_code >= 400:
            return VerifyResult(False, "Netlify turned that token down.")
        return VerifyResult(
            True,
            "Netlify is connected.",
            scope_note="The team can put your website online and update it.",
        )

    async def _resend(
        self, client: httpx.AsyncClient, values: dict[str, str]
    ) -> VerifyResult:
        key = values.get("RESEND_API_KEY", "")
        response = await client.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {key}"},
        )
        if response.status_code in (401, 403):
            return VerifyResult(
                False,
                "Resend didn't recognise that key.",
                hint="Copy the whole value, including the re_ at the start.",
            )
        if response.status_code >= 400:
            return VerifyResult(False, "Resend turned that key down.")

        verified = False
        try:
            body = response.json()
            entries = body.get("data", body) if isinstance(body, dict) else body
            verified = any(
                isinstance(d, dict) and d.get("status") == "verified"
                for d in (entries or [])
            )
        except ValueError:
            pass
        return VerifyResult(
            True,
            "Resend is connected.",
            scope_note=(
                "The team can send email from your own domain."
                if verified
                else "Until you verify a domain with Resend, email can only go "
                "to your own address — enough to see it working."
            ),
        )

    async def _stripe(
        self, client: httpx.AsyncClient, values: dict[str, str]
    ) -> VerifyResult:
        key = values.get("STRIPE_RESTRICTED_KEY", "")
        response = await client.get(
            "https://api.stripe.com/v1/balance",
            headers={"Authorization": f"Bearer {key}"},
        )
        if response.status_code == 401:
            return VerifyResult(
                False,
                "Stripe didn't recognise that key.",
                hint="Keys are shown once. Create another restricted key and "
                "copy the whole value.",
            )
        if response.status_code == 403:
            # A real key that simply isn't allowed to do this. Different
            # problem, different sentence, different fix.
            return VerifyResult(
                False,
                "That key works, but it isn't allowed to do enough.",
                hint="Edit the key in Stripe and give it Write on Products, "
                "Prices, Payment Links and Customers.",
            )
        if response.status_code >= 400:
            return VerifyResult(False, "Stripe turned that key down.")
        return VerifyResult(
            True,
            "Stripe is connected in test mode.",
            scope_note="The team can build a checkout and take pretend "
            "payments. No real money can move until you say so.",
        )

    async def _x402(
        self, client: httpx.AsyncClient, values: dict[str, str]
    ) -> VerifyResult:
        # Nothing cheap and safe to probe. Saying so is better than a green
        # tick that means nothing.
        if not values.get("X402_CDP_API_KEY_ID") or not values.get(
            "X402_CDP_API_KEY_SECRET"
        ):
            return VerifyResult(False, "Both halves of the key pair are needed.")
        return VerifyResult(
            True,
            "Saved. We can't check these with Coinbase from here, so the team "
            "will tell you the first time it uses them.",
            scope_note="Spending is off. The team can look up what other "
            "services charge, and nothing more.",
        )
