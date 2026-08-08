"""One engine, driven by a scripted model.

Werkhaus used to carry a second engine that replayed canned shifts, and the
tests used it because it was fast and free. It was also a parallel
implementation of the durable layer that could drift from the real one, and a
machine for producing convincing fiction — a founder watching it saw a team
reading pages nobody had opened.

The SDK ships ``TestLLM`` for exactly this. So the tests now run the *real*
engine — real brain, real budget layers, real halt semantics, real tool
executors — with a model that returns a fixed script. Nothing is faked except
the thinking, which is the only part that costs money.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from werkhaus.contract.models import CompanyStatus  # noqa: E402
from werkhaus.engines.verify import NullVerifier  # noqa: E402

RESEARCH = "market-research.md"


def _messages(*, files: bool = True):
    """A shift's worth of model turns: file the document, then finish."""
    from openhands.sdk import Message, TextContent
    from openhands.sdk.llm.message import MessageToolCall

    turns = []
    if files:
        turns.append(
            Message(
                role="assistant",
                content=[TextContent(text="Filing what I found.")],
                tool_calls=[
                    MessageToolCall(
                        id="call_1",
                        name="werkhaus_brain",
                        arguments=json.dumps(
                            {
                                "op": "record_artifact",
                                "path": RESEARCH,
                                "title": "Market research",
                                "summary": "What the research found.",
                                "confidence": "inferred",
                                "sources": [],
                            }
                        ),
                        origin="completion",
                    )
                ],
            )
        )
    turns.append(
        Message(
            role="assistant",
            content=[TextContent(text="Research is filed. Two findings.")],
        )
    )
    return turns


def scripted_llm(usage_id: str):
    """A fresh scripted model per shift, ending with a filed document.

    The document itself is written to disk by :func:`prepare_workspace` — the
    real employee writes it with her file editor, and scripting absolute paths
    into a canned model is noise rather than coverage. The file-editor interplay
    is covered in ``tests/sdk_seams``.
    """
    from openhands.sdk.testing import TestLLM

    return TestLLM.from_messages(_messages(), usage_id=usage_id)


def empty_llm(usage_id: str):
    """A shift that talks and files nothing. Our failure, not the founder's —
    used to prove such a shift is never charged against an allowance."""
    from openhands.sdk.testing import TestLLM

    return TestLLM.from_messages(_messages(files=False), usage_id=usage_id)


def make_engine(root: Path, *, llm=scripted_llm, verifier=None):
    """The real engine, with a scripted model and no browser."""
    from werkhaus.engines.openhands.engine import OpenHandsEngine

    engine = OpenHandsEngine(root=root, llm_factory=llm, browsing=False)
    engine.verifier = verifier or NullVerifier()
    return engine


async def started(root: Path, **kwargs):
    engine = make_engine(root, **kwargs)
    await engine.start()
    return engine


def prepare_workspace(root: Path, cid: str) -> Path:
    """What the scripted model needs on disk before its shift."""
    doc = Path(root) / cid / "workspace" / RESEARCH
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# Market research\n\nFindings.\n", encoding="utf-8")
    return doc


async def wait_idle(engine, cid: str, timeout: float = 30.0):
    """A shift is over when the company stops working. Deliberately says
    nothing about *how* it ended — that is the caller's assertion."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        company = await engine.get_company(cid)
        if company.status is not CompanyStatus.WORKING:
            return company
        await asyncio.sleep(0.05)
    raise AssertionError("shift never finished")


async def run_one_shift(engine, cid: str, root: Path):
    prepare_workspace(root, cid)
    await engine.start_shift(cid)
    return await wait_idle(engine, cid)


@pytest.fixture
def engine_root(tmp_path: Path) -> Path:
    return tmp_path
