"""Secret scanning, as a publish gate.

This runs over a snapshot that is about to become a public URL. It fails closed:
any hit and the link is never marked servable. A false positive costs someone a
support message; a false negative publishes an API key to the internet.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Named families first — these are unambiguous and worth reporting precisely.
PATTERNS: dict[str, re.Pattern[str]] = {
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    "model API key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{12,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "Stripe key": re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "JSON Web Token": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),
    "connection string with password": re.compile(
        r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s:/@]+@", re.I
    ),
    "absolute home path": re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+"),
    "assignment that looks like a secret": re.compile(
        r"\b(?:api[_-]?key|secret|password|passwd|token|credential)"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9_\-/+]{12,}",
        re.I,
    ),
}

# Entropy backstop for keys we have no pattern for.
ENTROPY_MIN_LENGTH = 28
ENTROPY_THRESHOLD = 4.2
_CANDIDATE = re.compile(r"[A-Za-z0-9+/_-]{" + str(ENTROPY_MIN_LENGTH) + r",}")

# Long non-secret strings that trip the entropy check.
_ENTROPY_ALLOW = re.compile(
    r"^(?:[a-z]+(?:[-_][a-z]+){2,}|(?:https?://)?[\w.-]+\.[a-z]{2,}(?:/\S*)?)$", re.I
)


def shannon(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    line: int
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}"


def scan_text(
    text: str, *, path: str = "<text>", extra: list[str] | None = None
) -> list[Finding]:
    """Scan one document. ``extra`` holds literal values that must never appear
    (the company's own secret registry), which no pattern could infer."""
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in PATTERNS.items():
            match = pattern.search(line)
            if match:
                findings.append(Finding(kind, path, number, _mask(match.group())))

        for literal in extra or []:
            if literal and len(literal) >= 8 and literal in line:
                findings.append(
                    Finding("known secret value", path, number, _mask(literal))
                )

        for candidate in _CANDIDATE.findall(line):
            if _ENTROPY_ALLOW.match(candidate):
                continue
            if shannon(candidate) >= ENTROPY_THRESHOLD:
                findings.append(
                    Finding("high-entropy string", path, number, _mask(candidate))
                )
    return findings


def scan_tree(root: Path, *, extra: list[str] | None = None) -> list[Finding]:
    """Scan every text file under ``root``. Used on a snapshot, never on a live
    company directory — the snapshot is what goes public."""
    findings: list[Finding] = []
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: not a text leak vector
        findings.extend(
            scan_text(text, path=str(file.relative_to(root)), extra=extra)
        )
    return findings


def _mask(value: str) -> str:
    """Never echo a secret back, not even into our own logs."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-2:]}"
