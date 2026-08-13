"""What a plan allows.

The free tier is not a smaller version of the product. It is the trial, and a
trial that stops before the founder can see something is worse than no trial:
they leave believing the product doesn't work. So the grant is sized by the arc
— enough shifts to reach a page they can show someone — not by a round number.

Three deliberate choices live here.

**The allowance is a projection, not a counter.** Nothing decrements. Usage is
counted from the shifts in the brain, the same way every other number in
Werkhaus is derived from the log. A crash mid-shift cannot leak a shift, and
there is no balance to drift out of sync with reality.

**A shift is only charged if it produced something.** A shift that burned its
budget and filed nothing is our failure, not the founder's, and billing a free
trial for it is how you turn a bad day into a lost user. This is the same rule
Maya works under: end the shift with something they can hold.

**Bring-your-own-key is a paid unlock.** Nobody arrives at a no-code tool
holding an API key; asking them to get one is the trial. It belongs where the
people who want it are — the second paid tier — and it buys a higher ceiling,
not a discount.

**The price lives here, next to what it buys.** One number, in one file, so the
front page cannot advertise a price the engine would not charge —
``tests/contract/test_pricing.py`` fails if the two ever disagree. Euros: the
model bills upstream are dollars, but a company selling in Europe quoting its
customers in dollars is asking them to do arithmetic before they can decide.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel

from werkhaus.contract.models import Autonomy, Base

Plan = str  # "free" | "studio" | "pro"

ALL_AUTONOMY: list[Autonomy] = [
    "full_auto",
    "semi_auto",
    "balanced",
    "limited",
    "full_control",
]

# Both ends of the dial spend faster than the middle — one on unattended
# shifts, the other on planning. A free trial cannot afford either, and
# running out at the far end is the version of running out that produces
# nothing to show for it.
FREE_AUTONOMY: list[Autonomy] = ["semi_auto", "balanced", "limited"]


class PlanLimits(BaseModel):
    """One row of the pricing table, in the only terms the engine cares about."""

    plan: Plan
    label: str
    price_eur: Decimal | None
    """Per month. None means free — not "ask us"."""
    price_year_eur: Decimal | None
    """Paid once, up front. Cheaper per month, and it is cash now."""
    pitch: str
    """Who this row is for, in one line, in the founder's language."""
    shift_grant: int | None
    """Shifts on joining. None means uncounted."""
    shift_refill: int
    """Shifts added each refill period."""
    refill_days: int
    byok: bool
    model_choice: bool
    autonomy: list[Autonomy]
    integrations: list[str] = []
    """Which services this plan may connect. Free gets the three with real
    free tiers, so a trial can reach a working product without anyone
    entering card details — money is the paid product's job."""

    external_spend: bool = False


PLANS: dict[Plan, PlanLimits] = {
    # Three shifts is the arc, not a round number: research, then the work
    # that turns it into a page, then one shift of slack for a thin result.
    # Re-measure once the full roster lands — the arc is what's fixed, the
    # integer follows it.
    "free": PlanLimits(
        plan="free",
        label="Free",
        price_eur=None,
        price_year_eur=None,
        pitch="Enough to leave with a folder you can show someone.",
        shift_grant=3,
        # Weekly, not daily: a shift a day is a working company, and a free
        # working company has no reason to become a paid one. Weekly is
        # enough to keep improving a site and nowhere near enough to run a
        # business on.
        shift_refill=1,
        refill_days=7,
        byok=False,
        model_choice=False,
        autonomy=FREE_AUTONOMY,
        integrations=["supabase", "netlify", "resend"],
        external_spend=False,
    ),
    "studio": PlanLimits(
        plan="studio",
        label="Studio",
        # Under every builder we are compared to, on purpose: they start at
        # $16 and $25 and they build the thing, which is the part a founder can
        # already get. Deciding what to build is the part they cannot, and it
        # should not be the expensive half of their stack.
        #
        # Founding price. It rises when a shift ends with a live page rather
        # than with documents, and whoever joined before then keeps this
        # number — which is the whole reason to buy a thing that is unfinished.
        price_eur=Decimal("12"),
        price_year_eur=Decimal("96"),
        pitch="A company you run every week, not a thing you tried once.",
        shift_grant=12,
        shift_refill=12,
        refill_days=30,
        byok=False,
        model_choice=False,
        autonomy=ALL_AUTONOMY,
        integrations=["supabase", "netlify", "resend", "stripe"],
        external_spend=True,
    ),
    "pro": PlanLimits(
        plan="pro",
        label="Pro",
        price_eur=Decimal("29"),
        price_year_eur=Decimal("240"),
        pitch="Your own key, your own model, no ceiling on shifts.",
        shift_grant=None,
        shift_refill=0,
        refill_days=0,
        byok=True,
        model_choice=True,
        autonomy=ALL_AUTONOMY,
        integrations=["supabase", "netlify", "resend", "stripe", "x402", "moonpay"],
        external_spend=True,
    ),
}

DEFAULT_PLAN = "pro"
"""Self-hosted and development runs are ungated. The hosted product sets
``WERKHAUS_PLAN`` per account; a metered default would mean every local demo
hits a paywall that exists for someone else's economics."""


def current_plan() -> PlanLimits:
    return PLANS.get(os.getenv("WERKHAUS_PLAN", DEFAULT_PLAN), PLANS[DEFAULT_PLAN])


def periods_elapsed(limits: PlanLimits, since: datetime, now: datetime) -> int:
    if limits.refill_days <= 0 or limits.shift_refill <= 0:
        return 0
    return max(0, (now - since).days // limits.refill_days)


def next_refill_at(
    limits: PlanLimits, since: datetime, now: datetime
) -> datetime | None:
    if limits.refill_days <= 0 or limits.shift_refill <= 0:
        return None
    return since + timedelta(
        days=limits.refill_days * (periods_elapsed(limits, since, now) + 1)
    )


def shifts_left(
    limits: PlanLimits, since: datetime, now: datetime, used: int
) -> int | None:
    """Entitlement minus what was actually spent, banked no higher than the
    original grant. Without the cap an account left alone for a year comes
    back with a year of shifts, which is a different product."""
    if limits.shift_grant is None:
        return None
    earned = limits.shift_grant + limits.shift_refill * periods_elapsed(
        limits, since, now
    )
    return max(0, min(earned - used, limits.shift_grant))


class Allowance(Base):
    """What the studio shows, and what the start button obeys."""

    plan: Plan
    label: str
    price_eur: Decimal | None
    """Per month. None means free — not "ask us"."""
    price_year_eur: Decimal | None
    """Paid once, up front. Cheaper per month, and it is cash now."""
    pitch: str
    """Who this row is for, in one line, in the founder's language."""
    shifts_left: int | None
    shifts_used: int
    grant: int | None
    refill: int
    refill_days: int
    next_refill_at: datetime | None
    byok: bool
    model_choice: bool
    autonomy: list[Autonomy]
    integrations: list[str]
    external_spend: bool


def build_allowance(
    limits: PlanLimits, since: datetime | None, used: int
) -> Allowance:
    now = datetime.now(UTC)
    start = since or now
    return Allowance(
        plan=limits.plan,
        label=limits.label,
        price_eur=limits.price_eur,
        price_year_eur=limits.price_year_eur,
        pitch=limits.pitch,
        shifts_left=shifts_left(limits, start, now, used),
        shifts_used=used,
        grant=limits.shift_grant,
        refill=limits.shift_refill,
        refill_days=limits.refill_days,
        next_refill_at=next_refill_at(limits, start, now),
        byok=limits.byok,
        model_choice=limits.model_choice,
        autonomy=limits.autonomy,
        integrations=limits.integrations,
        external_spend=limits.external_spend,
    )
