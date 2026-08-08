"""Operator commands.

Not a user-facing surface — the user never sees a terminal. This is for whoever
is on call when a projection looks wrong.
"""

from __future__ import annotations

import argparse
import json
import shutil
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

    reset = sub.add_parser(
        "reset",
        help="Delete every company in a data directory. For getting a clean "
        "slate before testing — it destroys work, so it asks first.",
    )
    reset.add_argument("data", type=Path)
    reset.add_argument(
        "--yes", action="store_true", help="Skip the confirmation prompt."
    )

    args = parser.parse_args(argv)

    if args.command == "reset":
        return _reset(args.data, assume_yes=args.yes)

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


def _reset(data: Path, *, assume_yes: bool = False) -> int:
    """Empty a data directory of companies.

    Deliberately not a `--force` flag on something else: deleting a founder's
    companies is its own verb, and it names what it is about to destroy before
    it does it.
    """
    if not data.exists():
        print(f"{data} doesn't exist; nothing to reset")
        return 0
    companies = sorted(d for d in data.glob("co_*") if d.is_dir())
    if not companies:
        print(f"{data} has no companies")
        return 0

    for directory in companies:
        name = directory.name
        try:
            store = BrainStore(directory, name)
            name = f"{name}  {store.state.name}"
        except Exception:
            pass  # unreadable is still deletable
        print(f"  {name}")
    if not assume_yes:
        answer = input(f"delete {len(companies)} companies from {data}? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("nothing deleted")
            return 1
    for directory in companies:
        shutil.rmtree(directory)
    print(f"deleted {len(companies)} companies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
