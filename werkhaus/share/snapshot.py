"""Building the thing a share link actually serves.

The live company directory is never served. ``publish`` copies an allowlist into
an immutable snapshot, scans it, and only then marks the link servable. The
public router has no code path that can reach ``companies/`` at all — which is
the point: a path-traversal bug in the public route cannot become a data breach
if the route has nothing to traverse to.

Allowlist, not denylist. ``notes/``, ``_state/``, ``workspace/`` and
``conversations/`` are never *enumerated*, not merely filtered out.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from werkhaus.brain.layout import CompanyPaths
from werkhaus.contract.errors import PublishBlocked
from werkhaus.contract.models import (
    Artifact,
    Decision,
    Objection,
    Progress,
    Role,
    Shift,
)
from werkhaus.share.scanner import Finding, scan_tree

logger = logging.getLogger(__name__)


@dataclass
class SnapshotResult:
    root: Path
    findings: list[Finding]

    @property
    def clean(self) -> bool:
        return not self.findings


def build_snapshot(
    *,
    company_root: Path,
    share_root: Path,
    token: str,
    company_name: str,
    one_liner: str,
    progress: Progress,
    roster: list[Role],
    shifts: list[Shift],
    artifacts: list[Artifact],
    decisions: list[Objection] | list[Decision],
    objections: list[Objection],
    include_shifts: bool = True,
    include_artifacts: bool = True,
    secret_values: list[str] | None = None,
) -> SnapshotResult:
    """Copy the allowlist into ``share_root/token`` and scan it.

    Raises :class:`PublishBlocked` if anything looks like a secret. The caller
    must not mark the link servable unless this returns cleanly.
    """
    paths = CompanyPaths(company_root)
    target = share_root / token
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    # Only artifacts the user explicitly opted in. Default is False, so silence
    # means private.
    public_artifacts = (
        [a for a in artifacts if a.public] if include_artifacts else []
    )

    (target / "artifacts").mkdir(exist_ok=True)
    copied: list[dict] = []
    for artifact in public_artifacts:
        source = (company_root / artifact.path).resolve()
        if not source.exists():
            continue
        if not source.is_relative_to(company_root.resolve()):
            logger.error(
                "artifact %s escapes the company root; skipped", artifact.path
            )
            continue
        destination = target / "artifacts" / f"{artifact.id}{_suffix(source)}"
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        copied.append({**artifact.model_dump(mode="json"), "file": destination.name})

    # Shift records are engine-generated and already scrubbed at write time.
    if include_shifts:
        (target / "shifts").mkdir(exist_ok=True)
        for shift in shifts:
            source = paths.shift_md(shift.number)
            if source.exists():
                shutil.copy2(source, target / "shifts" / source.name)

    manifest = {
        "company_name": company_name,
        "one_liner": one_liner,
        "progress": progress.model_dump(mode="json"),
        "roster": [r.model_dump(mode="json") for r in roster],
        "shifts": (
            [s.model_dump(mode="json") for s in shifts] if include_shifts else []
        ),
        "artifacts": copied,
        "decisions": [d.model_dump(mode="json") for d in decisions],
        "objections": [o.model_dump(mode="json") for o in objections],
        "published_at": datetime.now(UTC).isoformat(),
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    findings = scan_tree(target, extra=secret_values or [])
    if findings:
        # Fail closed, and do not leave the offending snapshot on disk.
        shutil.rmtree(target, ignore_errors=True)
        logger.error(
            "publish blocked for %s: %s",
            company_name,
            "; ".join(str(f) for f in findings[:5]),
        )
        raise PublishBlocked(
            "We found something private in this company's files, so we didn't "
            "publish it.",
            hint=(
                f"Look at {findings[0].path} — it contains something that looks "
                "like a {kind}.".format(kind=findings[0].kind)
            ),
        )

    return SnapshotResult(root=target, findings=[])


def _suffix(path: Path) -> str:
    return "" if path.is_dir() else path.suffix
