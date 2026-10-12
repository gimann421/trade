"""Append-only journal of paper-trading decisions: journal/YYYY-MM-DD.jsonl.

Every decision gets an entry, including holds, skips and orders the risk check
blocked, and every entry must say why.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from core.config import ROOT

JOURNAL_DIR = ROOT / "journal"
ACTIONS = ("submitted", "blocked", "error", "hold", "skip")


def record(action: str, reasoning: str, strategy: str, *, symbol=None, side=None, qty=None,
           price=None, hypothesis_id=None, risk_violations=None, order_id=None, extra=None,
           journal_dir: Path = JOURNAL_DIR) -> dict:
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    if not reasoning or not reasoning.strip():
        raise ValueError("every journal entry needs its reasoning")
    now = datetime.now(timezone.utc)
    entry = {
        "timestamp": now.isoformat(timespec="seconds"),
        "action": action,
        "strategy": strategy,
        "hypothesis_id": hypothesis_id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "reasoning": reasoning.strip(),
        "risk_violations": risk_violations or [],
        "order_id": order_id,
        "extra": extra or {},
    }
    journal_dir.mkdir(parents=True, exist_ok=True)
    with open(journal_dir / f"{now.date().isoformat()}.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read(day: str, journal_dir: Path = JOURNAL_DIR) -> list[dict]:
    path = journal_dir / f"{day}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
