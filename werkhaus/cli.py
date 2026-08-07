"""Operator commands.

Not a user-facing surface — the user never sees a terminal. This is for whoever
is on call when a projection looks wrong.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from werkhaus.brain.digest import render_digest
from werkhaus.brain.store import BrainStore
from werkhaus.share.scanner import scan_tree


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="werkhaus")
    sub = parser.add_subparsers(dest="command", required=True)

    rebuild = sub.add_parser(
        "rebuild",
        help="Replay a company's log and rewrite every projection. Safe to run "
        "any time: the log is the source of truth, projections are derived.",
    )
    rebuild.add_argument("company", type=Path)

    show = sub.add_parser("digest", help="Print what an employee would read.")
    show.add_argument("company", type=Path)
    show.add_argument("--role", default="researcher")
    show.add_argument("--budget", type=int, default=1200)

    scan = sub.add_parser("scan", help="Run the publish gate over a directory.")
    scan.add_argument("target", type=Path)

    facts = sub.add_parser("facts", help="Summarise a company's brain.")
    facts.add_argument("company", type=Path)

    args = parser.parse_args(argv)

    if args.command == "rebuild":
        store = _open(args.company)
        before = len(list(store.paths.projections.glob("*")))
        store.rebuild()
        after = len(list(store.paths.projections.glob("*")))
        print(f"replayed {store._seq} entries; projections {before} -> {after}")
        return 0

    if args.command == "digest":
        store = _open(args.company)
        print(render_digest(store, role_id=args.role, budget_tokens=args.budget))
        return 0

    if args.command == "scan":
        findings = scan_tree(args.target)
        for finding in findings:
            print(f"{finding}  ({finding.excerpt})")
        print(f"\n{len(findings)} finding(s)")
        return 1 if findings else 0

    if args.command == "facts":
        store = _open(args.company)
        state = store.state
        print(
            json.dumps(
                {
                    "name": state.name,
                    "log_entries": store._seq,
                    "shifts": len(state.shifts),
                    "tasks": {
                        "open": len(state.open_tasks),
                        "total": len(state.tasks),
                    },
                    "artifacts": len(state.artifacts),
                    "decisions": len(state.decisions),
                    "objections": len(state.objections),
                    "spent": str(state.spent),
                    "progress": state.progress.percent,
                },
                indent=2,
            )
        )
        return 0

    return 1


def _open(path: Path) -> BrainStore:
    if not (path / "_state" / "log.jsonl").exists():
        print(f"no company brain at {path}", file=sys.stderr)
        raise SystemExit(2)
    return BrainStore(path, path.name)


if __name__ == "__main__":
    raise SystemExit(main())
