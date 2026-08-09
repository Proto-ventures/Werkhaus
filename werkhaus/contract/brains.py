"""What the employees think with.

A company's brain is a model somewhere, reached with a key. Which one is a real
decision — free tiers differ by an order of magnitude, some models cannot call
tools at all and so cannot work a shift, and a founder who already pays for
inference somewhere should be able to point Werkhaus at it.

So this is a small catalog, in the same shape as the service catalog: named
providers with the key each needs and models known to work, plus one entry for
"something else that speaks OpenAI" — which is how a founder brings a gateway,
a router, a self-hosted server, or a platform like Swarms, without waiting for
us to add a card for it.

Two rules, both learned the hard way:

**A model that will not call tools cannot work a shift.** The whole loop is
tool calls; a model that answers in prose instead produces a shift that talks
and files nothing. Verification checks for the key, and the notes warn where a
plausible-looking model is a dead end.

**A key is checked before it is stored**, exactly like a service credential.
Finding out mid-shift costs a shift.
"""

from __future__ import annotations

from werkhaus.contract.models import Base

VAULT_MODEL = "WERKHAUS_MODEL"
VAULT_KEY = "WERKHAUS_MODEL_KEY"
VAULT_BASE_URL = "WERKHAUS_MODEL_BASE_URL"


class BrainProvider(Base):
    """One place a model can be reached."""

    id: str
    name: str
    prefix: str
    """The litellm prefix. ``WERKHAUS_MODEL`` is ``{prefix}/{model}``."""

    key_name: str
    """The vault name its key is stored under."""

    models: list[str] = []
    """Models known to work a shift — they call tools and hold a long context."""

    avoid: dict[str, str] = {}
    """Models that look right and are not, with the reason. Cheaper to write
    down than to have every founder discover it during a shift."""

    free_note: str = ""
    console_url: str = ""
    key_hint: str = ""
    openai_compatible: bool = True
    needs_base_url: bool = False
    probe_url: str = ""
    """Where to ask "does this key work". Empty means the OpenAI convention:
    ``{base_url}/models`` with a bearer token."""


GEMINI = BrainProvider(
    id="gemini",
    name="Google Gemini",
    prefix="gemini",
    key_name="GEMINI_API_KEY",
    models=[
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview",
    ],
    avoid={
        "gemini-flash-latest": "answers in prose instead of calling tools, so a "
        "shift talks and files nothing",
        "gemini-2.5-flash": "not available to keys issued in the newer AQ. "
        "format — use a 3.x flash instead",
    },
    free_note="The most generous free tier that can carry a shift: about 1,500 "
    "requests a day against a shift's 30–80, so roughly 15–20 shifts.",
    console_url="https://aistudio.google.com/apikey",
    key_hint="Starts with AIza or AQ.",
    openai_compatible=False,
    probe_url="https://generativelanguage.googleapis.com/v1beta/models",
)

OPENROUTER = BrainProvider(
    id="openrouter",
    name="OpenRouter",
    prefix="openrouter",
    key_name="OPENROUTER_API_KEY",
    models=[
        "qwen/qwen3-235b-a22b-2507",
        "deepseek/deepseek-chat",
        "google/gemini-2.0-flash-001",
    ],
    free_note="Free models are capped at 50 requests a day — under one shift. "
    "A one-time $10 raises it to 1,000.",
    console_url="https://openrouter.ai/keys",
    key_hint="Starts with sk-or-v1-",
    probe_url="https://openrouter.ai/api/v1/models",
)

GROQ = BrainProvider(
    id="groq",
    name="Groq",
    prefix="groq",
    key_name="GROQ_API_KEY",
    models=["llama-3.3-70b-versatile", "qwen/qwen3-32b"],
    free_note="Fast, and generous by the day — but 30 requests a minute, so a "
    "shift paces itself.",
    console_url="https://console.groq.com/keys",
    key_hint="Starts with gsk_",
    probe_url="https://api.groq.com/openai/v1/models",
)

CEREBRAS = BrainProvider(
    id="cerebras",
    name="Cerebras",
    prefix="cerebras",
    key_name="CEREBRAS_API_KEY",
    models=["llama-3.3-70b", "qwen-3-235b-a22b-instruct"],
    free_note="1M tokens a day, 30 requests a minute.",
    console_url="https://cloud.cerebras.ai",
    key_hint="Starts with csk-",
    probe_url="https://api.cerebras.ai/v1/models",
)

NVIDIA = BrainProvider(
    id="nvidia_nim",
    name="NVIDIA NIM",
    prefix="nvidia_nim",
    key_name="NVIDIA_NIM_API_KEY",
    models=[
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "moonshotai/kimi-k2-instruct",
    ],
    free_note="Free credits, throttled per minute. Popular models are often "
    "saturated — a quieter one finishes sooner.",
    console_url="https://build.nvidia.com",
    key_hint="Starts with nvapi-",
    probe_url="https://integrate.api.nvidia.com/v1/models",
)

OPENAI = BrainProvider(
    id="openai",
    name="OpenAI",
    prefix="openai",
    key_name="OPENAI_API_KEY",
    models=["gpt-4.1-mini", "gpt-4.1"],
    free_note="Paid. Reliable at tool calling, which is most of a shift.",
    console_url="https://platform.openai.com/api-keys",
    key_hint="Starts with sk-",
    probe_url="https://api.openai.com/v1/models",
)

ANTHROPIC = BrainProvider(
    id="anthropic",
    name="Anthropic",
    prefix="anthropic",
    key_name="ANTHROPIC_API_KEY",
    models=["claude-sonnet-4-5", "claude-haiku-4-5"],
    free_note="Paid.",
    console_url="https://console.anthropic.com/settings/keys",
    key_hint="Starts with sk-ant-",
    openai_compatible=False,
    probe_url="https://api.anthropic.com/v1/models",
)

CUSTOM = BrainProvider(
    id="custom",
    name="Something else",
    prefix="openai",
    key_name=VAULT_KEY,
    free_note="Anything that speaks the OpenAI API — a gateway, a router, a "
    "platform, a server of your own. Give it an address and a key.",
    key_hint="Whatever that service issued you",
    needs_base_url=True,
)
"""The escape hatch, and deliberately not a long tail of half-tested cards.

Most inference platforms speak the OpenAI protocol, so one honest entry covers
them all — including ones that do not exist yet. A founder pointing Werkhaus at
Swarms enters ``https://api.swarms.world/v1`` and their key; the litellm
``openai/`` prefix with a base URL does the rest.
"""

BRAINS: tuple[BrainProvider, ...] = (
    GEMINI,
    OPENROUTER,
    GROQ,
    CEREBRAS,
    NVIDIA,
    OPENAI,
    ANTHROPIC,
    CUSTOM,
)

BRAINS_BY_ID: dict[str, BrainProvider] = {b.id: b for b in BRAINS}


class BrainChoice(Base):
    """What a company is currently thinking with. Never the key itself."""

    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    key_hint: str | None = None
    """"51 characters, ends in …Bw" — the only echo a stored key ever gets."""

    configured: bool = False
    editable: bool = True
    """False on a plan without bring-your-own-key: the section still explains
    what it would do, exactly like the autonomy dial's withheld ends."""

    note: str | None = None


def provider_for(model: str) -> BrainProvider | None:
    """Which provider a ``prefix/model`` string belongs to."""
    prefix = model.split("/", 1)[0] if "/" in model else ""
    for brain in BRAINS:
        if brain.id != "custom" and brain.prefix == prefix:
            return brain
    return None
