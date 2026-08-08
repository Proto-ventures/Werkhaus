"""Model configuration for the real engine.

One knob: ``WERKHAUS_MODEL``, a litellm model string. The house preference is
open-weight models through providers like OpenRouter (``openrouter/<vendor>/<model>``
with ``OPENROUTER_API_KEY``) or NVIDIA NIM (``nvidia_nim/<model>`` with
``NVIDIA_NIM_API_KEY``); anything litellm can route works.

Cost honesty: open-weight models are often missing from litellm's price map, so
a run can report $0.00 while very much not being free. Set
``WERKHAUS_INPUT_COST_PER_MTOK`` / ``WERKHAUS_OUTPUT_COST_PER_MTOK`` to your
provider's prices and every budget layer uses them; without them, a token-based
estimate at conservative defaults keeps the meters honest-ish rather than
silent.
"""

from __future__ import annotations

import os
from decimal import Decimal

from openhands.sdk import LLM
from openhands.sdk.context.condenser import LLMSummarizingCondenser

from werkhaus.contract.errors import ValidationFailed

# Conservative defaults for the estimate fallback, dollars per million tokens.
DEFAULT_INPUT_PER_MTOK = 0.50
DEFAULT_OUTPUT_PER_MTOK = 2.00

# Provider prefix -> the env var litellm reads for it. Only used to fail early
# with a friendly message instead of mid-shift with a provider error.
_KEY_ENVS = {
    "openrouter": "OPENROUTER_API_KEY",
    "nvidia_nim": "NVIDIA_NIM_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "together_ai": "TOGETHERAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "github": "GITHUB_API_KEY",
}


def _cost_per_token(env: str, default_per_mtok: float) -> float:
    raw = os.getenv(env)
    return (float(raw) if raw else default_per_mtok) / 1_000_000


def check_model_config() -> None:
    """Called at engine start so a misconfigured server refuses to boot with a
    sentence a person can act on, instead of failing mid-shift."""
    model = os.getenv("WERKHAUS_MODEL", "").strip()
    if not model:
        raise ValidationFailed(
            "The company can't work yet — no employee brain is configured.",
            hint="Set WERKHAUS_MODEL to a model string, e.g. "
            "openrouter/qwen/qwen3-235b-a22b-2507 (with OPENROUTER_API_KEY set) "
            "or nvidia_nim/moonshotai/kimi-k2-instruct (with NVIDIA_NIM_API_KEY).",
        )
    provider = model.split("/", 1)[0]
    key_env = _KEY_ENVS.get(provider)
    if (
        key_env
        and not os.getenv(key_env)
        and not os.getenv("WERKHAUS_MODEL_KEY")
    ):
        raise ValidationFailed(
            "The employee brain has no key to work with.",
            hint=f"Set {key_env} (or WERKHAUS_MODEL_KEY) for {provider}.",
        )


def build_llm(usage_id: str) -> LLM:
    check_model_config()
    return LLM(
        model=os.environ["WERKHAUS_MODEL"].strip(),
        api_key=os.getenv("WERKHAUS_MODEL_KEY") or None,
        base_url=os.getenv("WERKHAUS_MODEL_BASE_URL") or None,
        usage_id=usage_id,
        input_cost_per_token=_cost_per_token(
            "WERKHAUS_INPUT_COST_PER_MTOK", DEFAULT_INPUT_PER_MTOK
        ),
        output_cost_per_token=_cost_per_token(
            "WERKHAUS_OUTPUT_COST_PER_MTOK", DEFAULT_OUTPUT_PER_MTOK
        ),
        # Free and trial tiers throttle by the minute. Patience is cheaper
        # than a failed shift: these defaults ride out a 60s window, and the
        # env knobs stretch further for tightly capped providers.
        num_retries=int(os.getenv("WERKHAUS_LLM_RETRIES", "6")),
        retry_min_wait=int(os.getenv("WERKHAUS_LLM_RETRY_MIN_WAIT", "10")),
        retry_max_wait=int(os.getenv("WERKHAUS_LLM_RETRY_MAX_WAIT", "90")),
    )


def build_condenser(llm: LLM) -> LLMSummarizingCondenser:
    """The preset's summarizing condenser, replicated: without one, a long
    research run dies on context length instead of forgetting gracefully."""
    return LLMSummarizingCondenser(
        llm=llm.model_copy(update={"usage_id": "condenser"}),
        max_size=80,
        keep_first=4,
    )


def estimate_cost(
    accumulated_cost: float, prompt_tokens: int, completion_tokens: int
) -> Decimal:
    """The real number when litellm knows the model's prices; a token-based
    estimate when it doesn't. Never silently zero after real work."""
    if accumulated_cost > 0:
        return Decimal(str(accumulated_cost))
    if prompt_tokens == 0 and completion_tokens == 0:
        return Decimal("0")
    input_rate = _cost_per_token("WERKHAUS_INPUT_COST_PER_MTOK", DEFAULT_INPUT_PER_MTOK)
    output_rate = _cost_per_token(
        "WERKHAUS_OUTPUT_COST_PER_MTOK", DEFAULT_OUTPUT_PER_MTOK
    )
    return Decimal(
        str(prompt_tokens * input_rate + completion_tokens * output_rate)
    )
