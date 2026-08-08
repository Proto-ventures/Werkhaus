"""Secret scanning, as a publish gate.

This runs over a snapshot that is about to become a public URL. It fails closed:
any hit and the link is never marked servable. A false positive costs someone a
support message; a false negative publishes an API key to the internet.
"""

from __future__ import annotations

import base64
import json
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
    "Stripe webhook signing secret": re.compile(r"\bwhsec_[A-Za-z0-9]{16,}"),
    "Supabase secret key": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{16,}"),
    "Supabase access token": re.compile(r"\bsbp_[A-Za-z0-9]{16,}"),
    "Netlify access token": re.compile(r"\bnfp_[A-Za-z0-9]{16,}"),
    "Resend API key": re.compile(r"\bre_[A-Za-z0-9]{8,}_[A-Za-z0-9]{16,}"),
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


# Credentials that are *meant* to ship in a browser bundle. Without this, a
# site that talks to its own database can never be published: Supabase's anon
# key is a JWT, and the JWT pattern above would block every page carrying one.
PUBLIC_PATTERNS: dict[str, re.Pattern[str]] = {
    "Stripe publishable key": re.compile(r"\bpk_(?:live|test)_[A-Za-z0-9]{16,}"),
    "Supabase publishable key": re.compile(r"\bsb_publishable_[A-Za-z0-9_-]{16,}"),
}

# The whole token, signature included: blanking only the header and payload
# leaves a high-entropy signature behind, which the entropy backstop then
# reports — and a legitimate page stays unpublishable for the wrong reason.
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.([A-Za-z0-9_-]{10,})\.[A-Za-z0-9_-]*")


def jwt_role(token: str) -> str | None:
    """The ``role`` claim of a JWT, read without verifying the signature.

    Supabase's anon key and its service_role key are both JWTs of the same
    shape and opposite meaning: one is designed to sit in a public page, the
    other is a database superuser that bypasses row-level security. Telling
    them apart by pattern is impossible; the claim is right there, so read it.
    """
    match = _JWT.search(token)
    if not match:
        return None
    payload = match.group(1)
    try:
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        role = json.loads(decoded).get("role")
    except Exception:
        return None
    return role if isinstance(role, str) else None


def _blank_public(line: str) -> str:
    """Replace declared-public credentials with spaces, preserving offsets."""
    def blank(match: re.Match[str]) -> str:
        return " " * len(match.group())

    for pattern in PUBLIC_PATTERNS.values():
        line = pattern.sub(blank, line)
    if jwt_role(line) == "anon":
        line = _JWT.sub(blank, line)
    return line


def _service_role_findings(line: str, path: str, number: int) -> list[Finding]:
    """The loudest finding this scanner has. A service_role key in a public
    file is not a leaked credential — it is a public database."""
    if jwt_role(line) != "service_role":
        return []
    match = _JWT.search(line)
    assert match is not None
    return [
        Finding(
            "Supabase service key (this one can read and write everything)",
            path,
            number,
            _mask(match.group()),
        )
    ]


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
    for number, raw_line in enumerate(text.splitlines(), 1):
        # A page that talks to a database has to carry a key, and that key is
        # published on purpose. Blank the credentials that are designed to be
        # public before anything looks at the line — including the entropy
        # backstop, which they would trip by construction.
        line = _blank_public(raw_line)
        for role_finding in _service_role_findings(raw_line, path, number):
            findings.append(role_finding)
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
