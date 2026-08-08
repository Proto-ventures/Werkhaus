"""A whole scripted shift through a real conversation.

This is the test that makes the seams honest: a real ``LocalConversation``, the
real tool registry, the real ``werkhaus_brain`` executor writing into a real
``BrainStore`` — only the model is scripted. If tool resolution, action
validation, the provenance cross-check, or the narrator break, they break here,
in two seconds, without a network.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

# The words that must never reach a user-facing string, from the API-level
# leak test — one list, one truth.
from tests.contract.test_api_stub import FORBIDDEN_WORDS  # noqa: E402
from werkhaus.brain.store import BrainStore  # noqa: E402
from werkhaus.contract.models import Charter, TaskStatus  # noqa: E402
from werkhaus.engines.bus import CompanyBus  # noqa: E402

VISITED = "https://visited.example/pricing"
NEVER_VISITED = "https://never-visited.example/about"


@pytest.fixture
def world(tmp_path):
    brain = BrainStore(tmp_path / "co_test", "co_test")
    brain.set_charter(
        Charter(
            idea="A ceramics subscription box",
            one_liner="A ceramics subscription box",
            audience="People who like nice objects",
            success_looks_like="A research report a stranger could act on.",
        ),
        "Test Co",
    )
    shift = brain.open_shift(number=1, agenda=["Research the market"])
    task = brain.add_task(
        title="Research the market", shift_id=shift.id, priority=2, actor="chief"
    )
    return brain, shift, task


async def test_scripted_shift_through_a_real_conversation(world) -> None:
    import openhands.tools.file_editor  # noqa: F401 — registers the tool
    from openhands.sdk import (
        Agent,
        LocalConversation,
        Message,
        TextContent,
        Tool,
    )
    from openhands.sdk.llm.message import MessageToolCall
    from openhands.sdk.testing import TestLLM

    import werkhaus.engines.openhands.brain_tool as bt
    from werkhaus.engines.openhands.narrator import Narrator

    brain, shift, task = world
    bus = CompanyBus("co_test", brain.paths.events)
    bus.bind_loop(asyncio.get_running_loop())

    ctx = bt.ShiftContext(
        company_id="co_test",
        shift_id=shift.id,
        role_id="researcher",
        shift_number=1,
        brain=brain,
        bus=bus,
    )
    bt.register_shift(ctx)
    # Maya "visited" exactly one page this shift.
    ctx.browsed_urls.add(bt.normalize_url(VISITED))

    doc = brain.paths.workspace / "market-research.md"

    def turn(i: int, name: str, args: dict, say: str) -> Message:
        return Message(
            role="assistant",
            content=[TextContent(text=say)],
            tool_calls=[
                MessageToolCall(
                    id=f"call_{i}",
                    name=name,
                    arguments=json.dumps(args),
                    origin="completion",
                )
            ],
        )

    script = [
        turn(1, "werkhaus_brain", {"op": "read_digest"}, "Reading the digest."),
        turn(
            2,
            "werkhaus_brain",
            {"op": "claim_task", "task_id": task.id},
            "Claiming my task.",
        ),
        turn(
            3,
            "file_editor",
            {
                "command": "create",
                "path": str(doc),
                "file_text": "# Market research\n\nTwo competitors found.\n",
            },
            "Writing it up.",
        ),
        turn(
            4,
            "werkhaus_brain",
            {
                "op": "record_artifact",
                "path": "market-research.md",
                "title": "Market research",
                "summary": "Two competitors, both cheaper.",
                "confidence": "sourced",
                "sources": [VISITED, NEVER_VISITED],
            },
            "Recording the document.",
        ),
        turn(
            5,
            "werkhaus_brain",
            {"op": "complete_task", "task_id": task.id},
            "Marking it done.",
        ),
        Message(
            role="assistant",
            content=[
                TextContent(
                    text="Done. Two competitors found, both priced lower than "
                    "we planned. I could not find churn numbers anywhere."
                )
            ],
        ),
    ]

    agent = Agent(
        llm=TestLLM.from_messages(script),
        tools=[
            Tool(name="file_editor"),
            Tool(name="werkhaus_brain", params={"company_id": "co_test"}),
        ],
        system_prompt_kwargs={"soul_content": "You are Maya, a test employee."},
    )
    conversation = LocalConversation(
        agent=agent,
        workspace=str(brain.paths.workspace),
        callbacks=[Narrator(ctx)],
        visualizer=None,
        max_iteration_per_run=20,
    )
    try:
        conversation.send_message("Shift 1 has started. Read the digest and work.")
        await asyncio.to_thread(conversation.run)
    finally:
        bt.unregister_shift("co_test")
    # Drain emissions queued from the worker thread onto the loop.
    await asyncio.sleep(0.05)

    # The brain saw the whole arc: claimed, done, recorded.
    assert brain.state.tasks[task.id].status is TaskStatus.DONE
    artifacts = list(brain.state.artifacts.values())
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.title == "Market research"
    assert artifact.path == "workspace/market-research.md"
    assert doc.read_text(encoding="utf-8").startswith("# Market research")

    # The provenance cross-check caught the lie: one of the two sources was
    # never visited, so "sourced" was downgraded, out loud.
    assert artifact.confidence == "inferred"

    # The executor and narrator told the story on the bus.
    events = bus.replay(0, 500)
    kinds = [e.kind.value for e in events]
    assert "task.claimed" in kinds
    assert "task.done" in kinds
    assert "artifact.created" in kinds

    # And nothing in it speaks the wrong vocabulary.
    for event in events:
        blob = f"{event.text} {event.detail or ''}".lower()
        assert "traceback" not in blob
        assert "/home/" not in blob and "/users/" not in blob
        for word in FORBIDDEN_WORDS:
            assert word not in blob, f"{word!r} leaked in: {blob}"


async def test_stopped_context_blocks_all_writes(world) -> None:
    """The discard guard: after halt, the tool refuses everything."""
    import werkhaus.engines.openhands.brain_tool as bt

    brain, shift, task = world
    bus = CompanyBus("co_test", brain.paths.events)
    bus.bind_loop(asyncio.get_running_loop())
    ctx = bt.ShiftContext(
        company_id="co_test",
        shift_id=shift.id,
        role_id="researcher",
        shift_number=1,
        brain=brain,
        bus=bus,
    )
    ctx.stopped.set()

    executor = bt.BrainExecutor(ctx)
    observation = executor(
        bt.BrainAction(op="claim_task", task_id=task.id), None
    )
    assert observation.is_error
    assert brain.state.tasks[task.id].status is TaskStatus.OPEN
