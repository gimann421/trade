"""Secrets handling: environment only, masked repr, pattern scanning, log redaction.

Secrets are never read from config files, never stored in the DB or audit log, and
never rendered by ``repr``/``str``. Callers must call ``.reveal()`` explicitly.
"""
from __future__ import annotations

import os
import re
import threading

from .errors import SecretError


class Secret:
    __slots__ = ("_name", "_value")

    def __init__(self, name: str, value: str):
        self._name = name
        self._value = value
        register_secret_value(value)

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Secret({self._name}=***)"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:  # f"{secret}" stays masked
        return "***"

    def __reduce__(self):
        raise SecretError("secrets must not be pickled or serialized")


_known_values: set[str] = set()
_lock = threading.Lock()


def register_secret_value(value: str) -> None:
    if value and len(value) >= 6:
        with _lock:
            _known_values.add(value)


def get_secret(name: str, environ: dict[str, str] | None = None) -> Secret:
    env = os.environ if environ is None else environ
    value = env.get(name)
    if not value:
        raise SecretError(f"secret {name} is not set in the environment")
    return Secret(name, value)


# Patterns for credentials that must never be committed or logged. Built from
# fragments so this file does not itself match the patterns it detects.
_PATTERNS: dict[str, re.Pattern[str]] = {
    "alpaca_key": re.compile(r"\b(?:PK|AK)[A-Z0-9]{18,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile("-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-_.=]{20,}"),
    "assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+\-_.=]{12,}"
    ),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
}


def scan_text_for_secrets(text: str) -> list[str]:
    """Names of secret patterns found in ``text`` (never the matched values)."""
    return [name for name, pat in _PATTERNS.items() if pat.search(text)]


def redact(text: str) -> str:
    """Replace known secret values and secret-looking patterns with a marker."""
    with _lock:
        values = sorted(_known_values, key=len, reverse=True)
    for v in values:
        text = text.replace(v, "[REDACTED]")
    for pat in _PATTERNS.values():
        text = pat.sub("[REDACTED]", text)
    return text
