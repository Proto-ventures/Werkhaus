"""The six services, described for someone who has never made an API key.

Every provider requires a human to create the account and mint the first
credential — there is no automated path from nothing to a working backend, and
there never will be, because signing up is an agreement a person makes. So the
walkthrough is not a convenience wrapped around the real feature; it *is* the
feature, and the prose below is the part of this product a competitor cannot
copy from a docs page.

Rules for writing these steps:

* Name the button they will click, in the words printed on it.
* Link straight to the page, never to a docs homepage.
* Warn before the surprise, not after: a key shown once, a two-factor prompt.
* Never explain what a token *is*. They do not need to know, and saying it
  makes the task feel like it belongs to someone more technical than them.
* Keep every step followable from its words alone. Pictures are a slot.
"""

from __future__ import annotations

from werkhaus.contract.credentials import CredentialClass as C
from werkhaus.contract.integrations import (
    Availability,
    Category,
    CredentialField,
    IntegrationSpec,
    Provider,
    WalkStep,
)

SUPABASE = IntegrationSpec(
    id="supabase",
    display_name="Supabase",
    category=Category.DATABASE,
    what_it_does="Where your customers, their accounts and everything they "
    "save actually live.",
    unlocks=[
        "Somewhere to keep signups, orders and customer accounts",
        "People can make an account and log in",
        "The website stops being a picture and starts working",
    ],
    employees=["engineer"],
    cost_note="Free to start, and everything the team builds first fits inside "
    "the free tier. It will ask before anything costs money.",
    minutes=4,
    fields=[
        CredentialField(
            name="SUPABASE_ACCESS_TOKEN",
            label="Your Supabase access token",
            kind=C.SECRET,
            pattern=r"^sbp_[A-Za-z0-9]{20,}$",
            help="Supabase tokens start with sbp_ — this looks like a "
            "different value. Copy the one from the account tokens page.",
        ),
        CredentialField(
            name="SUPABASE_PROJECT_REF",
            label="Project",
            kind=C.REFERENCE,
            required=False,
            secret_input=False,
            team_fills_it=True,
        ),
        CredentialField(
            name="SUPABASE_URL",
            label="Database address",
            kind=C.REFERENCE,
            required=False,
            secret_input=False,
            team_fills_it=True,
        ),
        CredentialField(
            name="SUPABASE_ANON_KEY",
            label="Public key",
            kind=C.PUBLIC,
            required=False,
            secret_input=False,
            team_fills_it=True,
        ),
    ],
    refuses=[
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_SECRET_KEY",
    ],
    steps=[
        WalkStep(
            title="Make a Supabase account",
            body="Supabase is where your business will keep its information. "
            "Signing in with GitHub or Google is the quickest way, and it's "
            "free — you won't be asked for a card.",
            link="https://supabase.com/dashboard/sign-up",
            link_label="Open Supabase",
            media="supabase/01-signup.png",
            media_alt="The Supabase sign-up page",
        ),
        WalkStep(
            title="Go to your access tokens",
            body="This page lives under your account rather than any one "
            "project. The link below goes straight to it.",
            link="https://supabase.com/dashboard/account/tokens",
            link_label="Open the tokens page",
            media="supabase/02-tokens.png",
            media_alt="The Supabase account tokens page",
        ),
        WalkStep(
            title="Generate a new token",
            body="Press Generate new token. Give it a name you'll recognise "
            "later — werkhaus works well — and confirm.",
            media="supabase/03-generate.png",
            media_alt="The generate new token dialog",
            warning="Supabase shows this value once and never again. Copy it "
            "now; if you lose it, you can delete it and make another.",
        ),
        WalkStep(
            title="Paste it here",
            body="Paste the token below. We'll check it with Supabase before "
            "saving anything, so you'll know immediately if it worked.",
            field="SUPABASE_ACCESS_TOKEN",
        ),
    ],
    verify_label="Check it works",
    docs_url="https://supabase.com/docs/guides/getting-started",
)

NETLIFY = IntegrationSpec(
    id="netlify",
    display_name="Netlify",
    category=Category.HOSTING,
    what_it_does="Puts your website on the internet at an address you can "
    "send to anyone.",
    unlocks=[
        "A real web address instead of a preview",
        "Every change the team makes goes live",
    ],
    employees=["engineer"],
    cost_note="Free. A paid plan only matters at serious traffic.",
    minutes=3,
    fields=[
        CredentialField(
            name="NETLIFY_PERSONAL_ACCESS_TOKEN",
            label="Your Netlify access token",
            kind=C.SECRET,
            pattern=r"^nfp_[A-Za-z0-9]{20,}$",
            help="Netlify tokens start with nfp_ — check you copied the "
            "personal access token rather than something else on that page.",
        ),
        CredentialField(
            name="NETLIFY_SITE_ID",
            label="Site",
            kind=C.REFERENCE,
            required=False,
            secret_input=False,
            team_fills_it=True,
        ),
    ],
    steps=[
        WalkStep(
            title="Make a Netlify account",
            body="Netlify is where your website will live. Signing up with "
            "GitHub, GitLab or email all work the same.",
            link="https://app.netlify.com/signup",
            link_label="Open Netlify",
            media="netlify/01-signup.png",
            media_alt="The Netlify sign-up page",
        ),
        WalkStep(
            title="Open your access tokens",
            body="The link below goes to the applications page in your user "
            "settings. The tokens are in the section called Personal access "
            "tokens.",
            link="https://app.netlify.com/user/applications#personal-access-tokens",
            link_label="Open the tokens page",
            media="netlify/02-tokens.png",
            media_alt="Netlify personal access tokens",
        ),
        WalkStep(
            title="Create a token",
            body="Press New access token, name it werkhaus, and generate it.",
            warning="Netlify also shows this only once.",
            media="netlify/03-new-token.png",
            media_alt="The new access token form",
        ),
        WalkStep(
            title="Paste it here",
            body="Paste the token below and we'll check it with Netlify "
            "before saving it.",
            field="NETLIFY_PERSONAL_ACCESS_TOKEN",
        ),
    ],
    docs_url="https://docs.netlify.com",
)

RESEND = IntegrationSpec(
    id="resend",
    display_name="Resend",
    category=Category.EMAIL,
    what_it_does="Sends email to your customers — the confirmation after "
    "someone signs up, the receipt after someone pays.",
    unlocks=[
        "People get a confirmation when they sign up",
        "Receipts and updates go out automatically",
    ],
    employees=["engineer"],
    cost_note="Free for the first few thousand emails a month.",
    minutes=3,
    fields=[
        CredentialField(
            name="RESEND_API_KEY",
            label="Your Resend key",
            kind=C.SECRET,
            pattern=r"^re_[A-Za-z0-9_]{16,}$",
            help="Resend keys start with re_.",
        ),
        CredentialField(
            name="RESEND_FROM",
            label="Send email from",
            kind=C.REFERENCE,
            required=False,
            secret_input=False,
            help="An address at a domain you've verified with Resend.",
        ),
    ],
    steps=[
        WalkStep(
            title="Make a Resend account",
            body="Resend is the service that will send your customers email.",
            link="https://resend.com/signup",
            link_label="Open Resend",
            media="resend/01-signup.png",
            media_alt="The Resend sign-up page",
        ),
        WalkStep(
            title="Create a key",
            body="Go to API Keys and press Create API Key. Name it werkhaus. "
            "Full access is fine — this key can only send email.",
            link="https://resend.com/api-keys",
            link_label="Open API keys",
            media="resend/02-create-key.png",
            media_alt="The Resend API keys page",
            warning="Shown once, like the others.",
        ),
        WalkStep(
            title="Paste it here",
            body="Paste the key below. Until you've verified a domain with "
            "Resend you can only send email to yourself, which is enough to "
            "see it working.",
            field="RESEND_API_KEY",
        ),
    ],
    docs_url="https://resend.com/docs",
)

STRIPE = IntegrationSpec(
    id="stripe",
    display_name="Stripe",
    category=Category.PAYMENTS,
    what_it_does="Takes card payments from your customers.",
    unlocks=[
        "A checkout that takes real cards",
        "Prices and products the team can change",
    ],
    employees=["engineer", "analyst"],
    cost_note="Free to set up. Stripe takes a percentage only when you "
    "actually get paid.",
    minutes=8,
    fields=[
        CredentialField(
            name="STRIPE_RESTRICTED_KEY",
            label="Your Stripe test key",
            kind=C.SECRET,
            # Test mode first, enforced by the shape of the value rather than
            # by a branch somewhere that could be forgotten. A live key does
            # not match, so it cannot be stored by accident.
            pattern=r"^rk_test_[A-Za-z0-9]{16,}$",
            help="That isn't a test key. We only take keys beginning rk_test_ "
            "for now — taking real money is a decision you make on purpose, "
            "not one the team makes for you.",
        ),
        CredentialField(
            name="STRIPE_PUBLISHABLE_KEY",
            label="Publishable key",
            kind=C.PUBLIC,
            required=False,
            secret_input=False,
            team_fills_it=True,
        ),
    ],
    refuses=["STRIPE_SECRET_KEY", "STRIPE_LIVE_KEY"],
    steps=[
        WalkStep(
            title="Make a Stripe account",
            body="Stripe handles the card payments. You can build and test a "
            "whole checkout before giving Stripe any business details — those "
            "are only needed the day you want real money to arrive.",
            link="https://dashboard.stripe.com/register",
            link_label="Open Stripe",
            media="stripe/01-register.png",
            media_alt="The Stripe sign-up page",
        ),
        WalkStep(
            title="Turn on assistant access",
            body="Stripe keeps this switched off until you say otherwise. "
            "Open the page below and enable it. It's the step people miss, "
            "and nothing works without it.",
            link="https://dashboard.stripe.com/settings/mcp",
            link_label="Open the setting",
            media="stripe/02-enable.png",
            media_alt="The Stripe assistant access setting",
        ),
        WalkStep(
            title="Create a test key",
            body="Open your test API keys and press Create restricted key. "
            "Name it werkhaus. Give it Write on Products, Prices, Payment "
            "Links and Customers, and leave everything else as None.",
            link="https://dashboard.stripe.com/test/apikeys",
            link_label="Open test API keys",
            media="stripe/03-restricted-key.png",
            media_alt="The Stripe restricted key form",
            warning="Stripe will send you a two-factor code partway through, "
            "so keep your phone nearby.",
        ),
        WalkStep(
            title="Paste it here",
            body="Click the key to copy it, then paste it below. It begins "
            "with rk_test_ — that prefix is how we know it can't move real "
            "money yet.",
            field="STRIPE_RESTRICTED_KEY",
        ),
    ],
    docs_url="https://docs.stripe.com/keys/restricted-api-keys",
)

X402 = IntegrationSpec(
    id="x402",
    display_name="x402",
    category=Category.PAYMENTS,
    availability=Availability.BETA,
    what_it_does="Lets your business pay, and be paid, in stablecoins by the "
    "call — the way software buys from other software.",
    unlocks=["Charge per request instead of per month"],
    employees=["engineer"],
    cost_note="Real money moves per call, which is exactly why it starts "
    "switched off.",
    minutes=10,
    fields=[
        CredentialField(
            name="X402_CDP_API_KEY_ID",
            label="Coinbase key id",
            kind=C.SECRET,
        ),
        CredentialField(
            name="X402_CDP_API_KEY_SECRET",
            label="Coinbase key secret",
            kind=C.SECRET,
        ),
        CredentialField(
            name="X402_WALLET_ADDRESS",
            label="Wallet",
            kind=C.REFERENCE,
            required=False,
            secret_input=False,
            team_fills_it=True,
        ),
    ],
    steps=[
        WalkStep(
            title="This one is still in testing",
            body="You can connect it, and the team can look up what other "
            "services charge. It cannot spend anything: a payment here travels "
            "inside the request itself, where we have nowhere to stop and ask "
            "you first. Until we do, spending stays off.",
            link="https://x402.org",
            link_label="Read about x402",
        ),
        WalkStep(
            title="Get Coinbase developer keys",
            body="x402 uses a Coinbase wallet so no private keys are ever "
            "kept here. Create a key pair in the developer portal.",
            link="https://portal.cdp.coinbase.com",
            link_label="Open the Coinbase portal",
            field="X402_CDP_API_KEY_ID",
        ),
        WalkStep(
            title="And the secret half",
            body="Paste the second half of the key pair below.",
            field="X402_CDP_API_KEY_SECRET",
        ),
    ],
    docs_url="https://docs.cdp.coinbase.com/x402",
)

MOONPAY = IntegrationSpec(
    id="moonpay",
    display_name="MoonPay",
    category=Category.PAYMENTS,
    availability=Availability.MANUAL_SETUP,
    what_it_does="Lets customers buy with a card and pay you in crypto, and "
    "is where Helio's payment links live now.",
    unlocks=["Card-to-crypto checkout"],
    employees=["engineer"],
    cost_note="Fees per transaction, set by MoonPay.",
    minutes=15,
    manual_note="MoonPay can't be connected from here yet. It needs its own "
    "program installed on your computer, a sign-in through your browser, and "
    "a wallet created on that machine — none of which we can do for you, and "
    "we'd rather say so than show a button that fails. If you want this now, "
    "the documentation below is accurate; tell the team and they'll work "
    "around it in the meantime.",
    docs_url="https://support.moonpay.com",
)

CATALOG: tuple[IntegrationSpec, ...] = (
    SUPABASE,
    NETLIFY,
    RESEND,
    STRIPE,
    X402,
    MOONPAY,
)

BY_ID: dict[Provider, IntegrationSpec] = {spec.id: spec for spec in CATALOG}


def spec(provider: str) -> IntegrationSpec:
    """The spec for a provider, or a KeyError the API turns into a 404."""
    return BY_ID[provider]  # type: ignore[index]


def field(provider: str, name: str) -> CredentialField | None:
    for candidate in spec(provider).fields:
        if candidate.name == name:
            return candidate
    return None


def refused_names() -> frozenset[str]:
    """Every credential the catalog declines by name, across all providers.

    A database master key bypasses row-level security entirely, and handing one
    to an agent is the specific mistake behind the best-known MCP data leak.
    Refusing it by name — in the guided flow *and* in the raw vault — means the
    dangerous configuration cannot be reached by accident.
    """
    return frozenset(name for entry in CATALOG for name in entry.refuses)
