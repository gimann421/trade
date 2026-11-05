"""Governance lock: the Constitution, risk limits, promotion criteria and owner
permissions are pinned by SHA-256. Any drift fails closed at boot.

Regenerating the lock (``python -m nexus lock``) is a deliberate human action that
produces a visible diff in version control. Agent-editable memory lives under
``nexus/memory`` and must never contain governed files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import CONFIG_DIR, GOVERNED_FILES
from .errors import GovernanceError

PACKAGE_DIR = Path(__file__).parent
LOCK_PATH = PACKAGE_DIR / "governance.lock.json"
MEMORY_DIR = PACKAGE_DIR / "memory"
CONSTITUTION_PATH = PACKAGE_DIR / "docs" / "01_CONSTITUTION.md"


def governed_paths(config_dir: Path = CONFIG_DIR, constitution: Path = CONSTITUTION_PATH) -> dict[str, Path]:
    paths = {f"config/{n}": config_dir / n for n in GOVERNED_FILES}
    paths["docs/01_CONSTITUTION.md"] = constitution
    return paths


def _sha256(path: Path) -> str:
    # Normalize line endings so a checkout on another OS does not trip the lock.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def compute_manifest(config_dir: Path = CONFIG_DIR, constitution: Path = CONSTITUTION_PATH) -> dict[str, str]:
    return {k: _sha256(p) for k, p in sorted(governed_paths(config_dir, constitution).items())}


def write_lock(lock_path: Path = LOCK_PATH, **kw) -> dict[str, str]:
    manifest = compute_manifest(**kw)
    lock_path.write_text(json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_lock(lock_path: Path = LOCK_PATH, **kw) -> dict[str, str]:
    if not lock_path.exists():
        raise GovernanceError("governance.lock.json is missing (fail closed)")
    expected = json.loads(lock_path.read_text(encoding="utf-8")).get("files", {})
    actual = compute_manifest(**kw)
    bad = sorted(k for k in set(expected) | set(actual) if expected.get(k) != actual.get(k))
    if bad:
        raise GovernanceError(f"governed files changed or unlocked: {', '.join(bad)}")
    return actual


def assert_memory_is_clean(memory_dir: Path = MEMORY_DIR, **kw) -> None:
    """Governed files must never live in agent-editable memory."""
    names = {p.name for p in governed_paths(**kw).values()}
    if memory_dir.exists():
        clash = sorted(p.name for p in memory_dir.rglob("*") if p.is_file() and p.name in names)
        if clash:
            raise GovernanceError(f"governed files found in agent-editable memory: {clash}")
