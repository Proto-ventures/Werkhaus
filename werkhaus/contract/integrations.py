"""What a company is connected to.

Werkhaus builds real backends, and every real backend needs credentials the
founder alone can create: no API can sign up for a Supabase account, pass
Stripe's identity checks, or accept terms on someone's behalf. That boundary is
permanent, so the product is built around it rather than pretending it away —
the team asks for exactly one credential, at the moment it needs it, with
directions precise enough to follow without knowing what an API key is.

Three rules shape the models here.

**A key is verified before it is stored.** A credential that fails halfway
through a shift costs a shift, and on the free plan a founder only has three.
Nothing reaches the vault until the provider itself has confirmed it works.

**Connection state is derived, never recorded.** What we hold is in the vault;
what happened is in the log; the status is computed from both. There is no
"connected" flag to drift out of agreement with reality.

**A card never claims more than it can do.** Providers whose servers cannot be
driven headlessly say so on their own card instead of failing later.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field

from werkhaus.contract.credentials import CredentialClass
from werkhaus.contract.models import Base, RoleId, ShiftId

Provider = Literal["supabase", "stripe", "netlify", "resend", "x402", "moonpay"]

PROVIDERS: tuple[Provider, ...] = (
    "supabase",
    "stripe",
    "netlify",
    "resend",
    "x402",
    "moonpay",
)


class Category(StrEnum):
    DATABASE = "database"
    PAYMENTS = "payments"
    HOSTING = "hosting"
    EMAIL = "email"


class Availability(StrEnum):
    AVAILABLE = "available"
    """Works today, unattended, with a key the founder can get in minutes."""

    BETA = "beta"
    """Real, but not something to hand a company's money to yet."""

    MANUAL_SETUP = "manual_setup"
    """Needs work on the founder's own computer that we cannot do for them.
    Listed honestly rather than omitted, and never claimed as connected."""


class CredentialField(Base):
    """One value the founder pastes in, or the team discovers later."""

    name: str
    """The vault name. Also what :func:`werkhaus.contract.credentials.classify`
    keys on, so it must be listed there."""

    label: str
    kind: CredentialClass
    required: bool = True
    pattern: str | None = None
    """Anchored regex, checked in the browser and again on the server. This is
    where "test mode first" is enforced for Stripe: a live key simply does not
    match, so no code branch can forget it."""

    help: str = ""
    """One sentence, shown when the value is refused. Plain language."""

    secret_input: bool = True
    team_fills_it: bool = False
    """The team writes this one during a shift — a project id, a site id, the
    publishable key it fetched. Never asked of the founder."""


class WalkStep(Base):
    """One step of the guided walkthrough.

    Prose only, never a command. Each step must stand on its own words: the
    picture is an illustration, not the instruction, so a walkthrough with no
    pictures yet is still followable. Enforced by a test.
    """

    title: str
    body: str
    link: str | None = None
    link_label: str | None = None
    media: str | None = None
    """Filename under ``/walkthroughs/``. A slot — the page hides it if the
    file isn't there, so screen recordings can be added later without code."""

    media_alt: str | None = None
    field: str | None = None
    """The :class:`CredentialField` collected on this step, if any."""

    warning: str | None = None
    """Something that will surprise them if unsaid — a key shown only once, a
    two-factor prompt arriving mid-flow."""


class IntegrationSpec(Base):
    """A service, described in the founder's terms rather than the vendor's."""

    id: Provider
    display_name: str
    category: Category
    availability: Availability = Availability.AVAILABLE

    what_it_does: str
    """One sentence about their business, not about the technology."""

    unlocks: list[str] = Field(default_factory=list)
    """What the team can do once this exists, in plain words."""

    employees: list[RoleId] = Field(default_factory=list)
    cost_note: str = ""
    minutes: int = 5
    """An honest estimate of how long the walkthrough takes."""

    fields: list[CredentialField] = Field(default_factory=list)
    refuses: list[str] = Field(default_factory=list)
    """Credential names we decline by name. A database master key is the one
    credential whose misuse has already caused a real-world leak, so it is
    refused mechanically rather than discouraged in a paragraph."""

    steps: list[WalkStep] = Field(default_factory=list)
    verify_label: str = "Check it works"
    docs_url: str | None = None
    manual_note: str | None = None
    """Why this one can't be finished here, when availability says so."""


class ConnectionStatus(StrEnum):
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    NEEDS_ATTENTION = "needs_attention"
    """Worked once, stopped working. The team keeps going without it."""

    UNAVAILABLE = "unavailable"
    """Not on this plan, or needs setup we can't do from here."""


class Connection(Base):
    """Derived at read time from the vault, the log, and the plan."""

    provider: Provider
    status: ConnectionStatus
    fields_present: list[str] = Field(default_factory=list)
    hints: dict[str, str] = Field(default_factory=dict)
    """``name -> "44 characters, ends in …9f"``. The only echo of a stored
    value that exists anywhere in Werkhaus."""

    connected_at: datetime | None = None
    verified_at: datetime | None = None
    message: str | None = None
    """User prose about the last thing that happened, good or bad."""

    scope_note: str | None = None
    """What this key lets the team do, and what it doesn't."""

    blocks: list[str] = Field(default_factory=list)
    """Work this connection is holding up, so a card is never abstract."""

    unavailable_reason: str | None = None


class IntegrationState(Base):
    """Spec and connection together: one payload the page can render whole."""

    spec: IntegrationSpec
    connection: Connection


class ProvisionedResource(Base):
    """Something the team made that the founder now owns.

    Recorded so the studio can show a real address instead of a placeholder,
    and so a second shift knows the first one already built this.
    """

    id: str
    provider: Provider
    kind: Literal["project", "site", "deployment", "function", "bucket", "payment_link"]
    ref: str
    label: str
    """"Your database" — what it is to them, not what it is called."""

    url: str | None = None
    created_in_shift: ShiftId | None = None
    at: datetime


class SpendPolicy(Base):
    """What the team may spend on *services*, as distinct from thinking.

    Separate from the budget because it is a different kind of money: the LLM
    bill is ours to meter, a Supabase project on a paid tier is a recurring
    charge on the founder's own card. Everything here is off by default —
    Supabase, Netlify and Resend all have free tiers a whole product fits in.
    """

    external_cap: Decimal = Decimal("0.00")
    allow_paid_signup: bool = False
    x402_per_call_cap: Decimal = Decimal("0.10")
    x402_shift_cap: Decimal = Decimal("1.00")
    allow_x402: bool = False
    stripe_mode: Literal["test", "live"] = "test"


class BuildStep(Base):
    """One step of getting from an idea to a working product.

    Lives here rather than with the templates because it is what makes a
    connection card concrete: a card that says "this is holding up: Take a
    payment" is an argument, where "connect Stripe" is only a chore.
    """

    id: str
    title: str
    needs: list[Provider] = Field(default_factory=list)


BACKEND_STEPS: tuple[BuildStep, ...] = (
    BuildStep(id="site", title="Put a real page up"),
    BuildStep(id="db", title="Create the database", needs=["supabase"]),
    BuildStep(id="schema", title="Make somewhere to store signups", needs=["supabase"]),
    BuildStep(
        id="wire", title="Connect the page to the database", needs=["supabase"]
    ),
    BuildStep(id="deploy", title="Put it on the internet", needs=["netlify"]),
    BuildStep(
        id="email", title="Send people a confirmation", needs=["resend", "supabase"]
    ),
    BuildStep(id="pay", title="Take a payment", needs=["stripe"]),
)
