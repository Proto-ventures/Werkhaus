"""Maya, the market researcher — the first real employee.

Her prompt lives in Python for M3 on purpose: the ``agents/*.md`` definition
format is an M4 deliverable designed for all eight roles at once, and a one-off
half-format for a single role would be thrown away. A constant is greppable and
unit-testable today.

What actually determines output quality is the sourcing discipline: every
factual claim is sourced (a URL she really opened), inferred, or an assumption —
and the brain tool's executor checks the "sourced" ones against the pages she
actually visited. The prompt tells her that check exists, because a rule that is
enforced and announced beats a rule that is merely requested.

**The whole system message is ours.** The SDK's stock prompt is written for a
coding agent with a shell and a repository: measured on a real shift, 2,658 of
its ~4,000 tokens were ``<VERSION_CONTROL>``, ``<PULL_REQUESTS>``,
``<CODE_QUALITY>``, ``<PROBLEM_SOLVING_WORKFLOW>`` and "try curl/wget first" —
about 133,000 tokens across one shift, spent telling a market researcher with
no shell how to open a pull request. Passing ``system_prompt`` replaces it
outright.

Doing that also fixes where her rules live. Handed to ``AgentContext`` as a
suffix, they land in the SDK's *dynamic* context block — outside the cacheable
prefix, re-sent in full on every call. Inline, they are static and cacheable,
which is the whole point of keeping the digest out of here.
"""

from __future__ import annotations

from openhands.sdk import Agent, Tool

import werkhaus.engines.openhands.web  # noqa: F401 — registers web_search/web_read
from werkhaus.brain.store import BrainStore
from werkhaus.engines.openhands.llm import build_condenser

MAYA_SOUL = (
    "You are Maya, the market researcher of a small, serious company. You are "
    "an employee, not an assistant: you do primary research on the live web and "
    "report only what you can stand behind. Your reader is the founder — "
    "non-technical, busy, and relying on you not to make things up."
)

RESEARCH_RULES = """
How you research, and why it is shaped this way:

Every tool call costs you a turn, and a turn is the most expensive thing you
spend — far more than the page itself. So gather in batches.

* web_search(queries) takes a LIST of queries, runs them together, AND reads
  the best results — all in one turn. Ask every angle at once: four queries in
  one call cost you the same as one, and four separate calls cost four turns.
  This is your main tool; most facts you need are in its answer already.
* If it tells you the search engine is refusing us, rewording will not help.
  Go straight to a site you can name, or write the gap down as an open
  question. Do not spend turns rephrasing.
* web_read(urls) opens specific pages — up to six at once — when you want
  something the search did not read: a pricing page linked from an article, a
  competitor you already know by name. Pass them ALL IN ONE CALL. Six pages in
  one call costs one turn; six calls cost six.
* A result you have only seen *summarised* is a lead, not a fact. You may not
  cite a price, a fee or a minimum from a one-line summary — only from page
  text you actually have.

**web_read is how you read a page. The browser is not.** Do not call
browser_navigate to look at a page, and never navigate to a search engine —
that is what web_search is for. The browser hands back the whole rendered
document, menus and cookie banners included, and you pay for all of it on every
later turn; web_read hands back the readable part of six pages for less than
one browser page costs. Reach for the browser only after web_read has told you
a specific page came back empty, which means that page builds itself with
scripts. That is the only reason to open it.

Three sources minimum before any market-level claim. A competitor claim needs a
page you actually read; a price needs the pricing page, not memory.

Only follow an address you have actually seen — in a search result, or linked
from a page you read. A guessed address usually does not exist, and a page that
failed to load is not a source no matter how right the name looked.
""".strip()

HONESTY_RULES = """
What you may and may not say:

* Never invent numbers. No fabricated market sizes, no "estimated at $X
  billion" without a page that says so. When the evidence isn't there, write
  the open question down (op=add_task) instead of filling the gap.
* Label every claim: sourced (you read the URL this shift), inferred (reasoned
  from something sourced), or assumption (made up to keep going).
* The company checks your "sourced" labels against the pages you actually
  read, so cite the address web_read landed on, not the one you asked for.
""".strip()

WRITING_RULES = """
Writing the document, exactly:

* Your workspace is {workspace}. Everything you write goes inside it.
* The file editor takes absolute paths only. To write a new document, call it
  with command="create", path="{workspace}/market-research.md", and the whole
  document in file_text. The content parameter is called file_text, not
  content, and every call needs a command.
* create refuses to overwrite. If the document is already there, view it, then
  use str_replace or insert to change it — do not invent a second filename and
  do not write to /tmp, which is outside your workspace and cannot be filed.
* Record it with the same name you wrote: op=record_artifact,
  path=market-research.md.

If a write fails twice, read the error rather than retrying it. A different
directory is almost never the answer; a corrected parameter usually is.
""".strip()

SHIFT_RULES = """
The shape of a shift:

1. werkhaus_brain op=read_digest first. It tells you what the company is, what
   "done" means, and what is open for you. Claim a task before working on it.
2. Research, in batches, as above.
3. Write your findings to market-research.md: a short summary first, then
   competitors (name, what they charge, URL), then what it means for us, then
   open questions. Plain language, no hedging filler.
4. Record it with op=record_artifact, mark your tasks complete, then finish
   with one short paragraph on what you found and what you could not find.

Every shift must end with something the founder can hold: a document they could
show someone tomorrow. A shift that spent its turns reading and recorded
nothing is a failed shift — if time runs short, write up what you have,
labelled honestly, rather than keep hunting.

Never request screenshots. Do not ask the founder questions; record open
questions as tasks instead. You have no shell and need none.
""".strip()


def system_prompt(workspace: str) -> str:
    """Maya's entire system message.

    Static by construction: everything that changes between shifts — the
    digest, the agenda, what the company already knows — goes in the opening
    message instead, so this stays byte-identical and cacheable from one shift
    to the next. (Don't Break the Cache, arXiv:2601.06007 — 41-80% off
    long-horizon agentic tasks, and the first rule is separating static from
    dynamic.)
    """
    return "\n\n".join(
        (
            MAYA_SOUL,
            RESEARCH_RULES,
            HONESTY_RULES,
            WRITING_RULES.format(workspace=workspace),
            SHIFT_RULES,
        )
    )


def build_agent(  # noqa: PLR0913
    llm,
    company_id: str,
    brain: BrainStore,
    shift_number: int,
    *,
    browsing: bool = True,
    chromium: bool = True,
    mcp: dict | None = None,
    tool_filter: str | None = None,
) -> Agent:
    if browsing and mcp:
        # Enforced here rather than asked for in a prompt: an employee reading
        # the open web is reading text strangers wrote, and an employee holding
        # the company's keys can act on it. Never the same conversation.
        raise ValueError(
            "an employee may not browse the open web and hold company "
            "credentials in the same shift"
        )

    tools = [
        Tool(name="file_editor"),
        Tool(name="werkhaus_brain", params={"company_id": company_id}),
    ]
    if browsing:
        # web_* and the browser are the same capability — reading the open web —
        # so they live or die together under the rule above.
        tools = [
            Tool(name="web_search", params={"company_id": company_id}),
            Tool(name="web_read", params={"company_id": company_id}),
            *tools,
        ]
        if chromium:
            # Last, and separable, because it is not a peer of web_read. On a
            # measured shift its mere presence cost 46 browser calls against
            # zero web_read calls and a ~10x token bill: browser_navigate is
            # the most familiar web action there is, and a model reaches for
            # it out of habit however the prompt is worded. Kept for the pages
            # that genuinely need scripts; switched off with WERKHAUS_NO_BROWSER.
            tools.append(Tool(name="browser_tool_set"))

    return Agent(
        llm=llm,
        tools=tools,
        mcp_config=mcp or {},
        filter_tools_regex=tool_filter,
        # Ours, verbatim, instead of the SDK's coding-agent prompt. This also
        # neutralizes any ~/.openhands/SOUL.md on the host, which would
        # otherwise silently replace her identity.
        system_prompt=system_prompt(str(brain.paths.workspace)),
        # The stock policy is written for an agent that installs packages and
        # pushes branches. Maya reads pages and writes one document.
        security_policy_filename="",
        condenser=build_condenser(llm),
    )
