"""The real engine.

The engine. Contract, brain and bus are the shared ones; what differs is
that shift work comes from an actual model holding actual tools. In M3 that
means one employee: Maya, the market researcher, browsing the real web.

Everything imported from ``openhands.*`` stays under this package. The API, the
contract and the brain never see it.
"""

from __future__ import annotations

import asyncio
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from werkhaus.brain.store import BrainStore
from werkhaus.contract.brains import VAULT_BASE_URL, provider_for
from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.contract.models import Charter, Company, CompanyId, Shift
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.common import BaseEngine, CompanyRuntime, name_from_idea
from werkhaus.engines.openhands.runtime import OpenHandsCompany

logger = logging.getLogger(__name__)


class OpenHandsEngine(BaseEngine):
    def __init__(
        self,
        root: str | Path = "./data",
        llm_factory: Any = None,
        browsing: bool | None = None,
    ) -> None:
        super().__init__(root)
        # Test seam: contract tests inject a scripted model here. Real runs
        # build from WERKHAUS_MODEL.
        self.llm_factory = llm_factory
        if browsing is None:
            browsing = os.getenv("WERKHAUS_NO_BROWSER", "").lower() not in (
                "1",
                "true",
                "yes",
            )
        self.browsing = browsing

    # ------------------------------------------------------------------ byok
    VAULT_KEY = "WERKHAUS_MODEL_KEY"
    VAULT_MODEL = "WERKHAUS_MODEL"

    def byok(
        self, company: CompanyRuntime
    ) -> tuple[str | None, str | None, str | None]:
        """The founder's own key and model, if their plan includes that.

        Off-plan the vault entry is ignored rather than rejected: someone who
        upgrades should find the key they already saved simply working, and
        someone who downgrades should not have their company break — it goes
        back to running on ours.
        """
        allowance = self.allowance()
        if not allowance.byok:
            return None, None, None
        vault = self._vault_read(company)
        model = base_url = None
        if allowance.model_choice:
            model = (vault.get(self.VAULT_MODEL) or {}).get("value") or None
            base_url = (vault.get(VAULT_BASE_URL) or {}).get("value") or None
        # The key lives under the provider's own name, so a founder who
        # switches provider and switches back finds the old one still there.
        brain = provider_for(model or "")
        names = [brain.key_name] if brain else []
        names.append(self.VAULT_KEY)
        key = next(
            (v for n in names if (v := (vault.get(n) or {}).get("value"))), None
        )
        return key, model, base_url

    # -------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        # An inherited automation callback would make the workspace phone an
        # external URL when a conversation ends. Never in this process.
        os.environ.pop("AUTOMATION_CALLBACK_URL", None)
        os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

        # Importing registers the tools with the SDK's global registry.
        import openhands.tools.file_editor  # noqa: F401

        import werkhaus.engines.openhands.brain_tool  # noqa: F401

        if self.browsing:
            import openhands.tools.browser_use  # noqa: F401

        if self.llm_factory is None:
            # Fail at boot with a sentence a person can act on, not mid-shift
            # with a provider error.
            from werkhaus.engines.openhands.llm import check_model_config

            check_model_config()

        await super().start()

    def _make_runtime(self, brain: BrainStore, bus: CompanyBus) -> OpenHandsCompany:
        return OpenHandsCompany(brain, bus)

    # --------------------------------------------------------------- companies
    async def create_company(self, idea: str, name: str | None = None) -> Company:
        idea = idea.strip()
        # Deterministic and free: no model call at creation time. The charter
        # fields the guided capture doesn't fill yet say plainly that they are
        # unfilled — research exists to fill them.
        charter = Charter(
            idea=idea,
            one_liner=idea if len(idea) <= 140 else idea[:139] + "…",
            audience="Not settled yet. The first research shift narrows this.",
            success_looks_like=(
                "A market-research report a stranger could act on."
            ),
        )
        company = self._new_company(
            charter=charter,
            name=name or name_from_idea(idea),
            budget_cap=Decimal(os.getenv("WERKHAUS_BUDGET_CAP", "20.00")),
            per_shift_cap=Decimal(os.getenv("WERKHAUS_SHIFT_CAP", "2.00")),
        )
        return company.company()

    # ------------------------------------------------------------------ shifts
    async def start_shift(
        self, cid: CompanyId, focus: str | None = None, *, auto: bool = False
    ) -> Shift:
        from werkhaus.engines.openhands.shift import DEFAULT_AGENDA, run_shift

        company = self._get(cid)
        assert isinstance(company, OpenHandsCompany)
        self._ensure_can_start(company)
        if not auto:
            company.brain.record_metric("auto_chained", 0)

        if focus:
            agenda = [focus.strip()]
        else:
            open_tasks = sorted(
                company.brain.state.open_tasks, key=lambda t: t.priority
            )[:3]
            agenda = [t.title for t in open_tasks] or list(DEFAULT_AGENDA)

        shift = company.brain.open_shift(
            number=len(company.brain.state.shifts) + 1, agenda=agenda
        )
        company.task_handle = asyncio.create_task(run_shift(self, company, shift.id))
        return shift

    # ------------------------------------------------------------------- halt
    async def _cancel(self, company: CompanyRuntime) -> None:
        """The kill switch, real-engine flavour.

        The worker thread cannot be interrupted mid-LLM-call, so we don't try:
        set the discard guard (no brain writes, no bus emissions can get
        through), ask the run to pause between steps, close the shift now, and
        let the thread drain into silence.
        """
        assert isinstance(company, OpenHandsCompany)
        ctx = company.shift_ctx
        if ctx is not None:
            ctx.stopped.set()
        conversation = company.conversation
        if conversation is not None:
            try:
                conversation.pause()
            except Exception:
                logger.debug("pause on cancel failed", exc_info=True)

        for shift in company.brain.abort_running_shifts("You stopped this shift."):
            company.bus.emit(
                K.SHIFT_FAILED,
                f"Shift {shift.number} was stopped. "
                "Everything already done is saved.",
                shift_id=shift.id,
            )
        await super()._cancel(company)
