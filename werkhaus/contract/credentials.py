"""Which stored values are secret, and which are meant to be seen.

A page that talks to a database has to carry a key. Supabase's anon key and
Stripe's publishable key are designed to ship inside a public web page; the
access token that created the project, and the key that bypasses row-level
security, are not. The publish gate needs to tell them apart, because treating
every stored value as secret makes a working site unpublishable, and treating
every stored value as public publishes a database.

The rule is one-directional and fails closed: a value is public only because
something here says it is. Anything else — including every name a founder types
into the vault by hand — is secret.
"""

from __future__ import annotations

from enum import StrEnum


class CredentialClass(StrEnum):
    PUBLIC = "public"
    """Designed to appear in a browser bundle. Never blocks a publish."""

    SECRET = "secret"
    """Never leaves the server. Blocks a publish wherever it appears."""

    REFERENCE = "reference"
    """Not a credential at all — an id, a URL, a project ref."""


PUBLIC_NAMES: frozenset[str] = frozenset(
    {
        "SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "STRIPE_PUBLISHABLE_KEY",
    }
)

REFERENCE_NAMES: frozenset[str] = frozenset(
    {
        "SUPABASE_URL",
        "SUPABASE_PROJECT_REF",
        "NETLIFY_SITE_ID",
        "RESEND_FROM",
        "STRIPE_PAYMENT_LINK",
        "X402_WALLET_ADDRESS",
        "WERKHAUS_MODEL",
        "WERKHAUS_MODEL_BASE_URL",
    }
)


def classify(name: str) -> CredentialClass:
    """Total, and secret by default.

    Guessing wrong in one direction costs a support message; guessing wrong in
    the other publishes a key to the internet.
    """
    upper = name.strip().upper()
    if upper in PUBLIC_NAMES:
        return CredentialClass.PUBLIC
    if upper in REFERENCE_NAMES:
        return CredentialClass.REFERENCE
    return CredentialClass.SECRET
