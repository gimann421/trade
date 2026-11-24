"""Long-term JUDGMENT track for the owner's real account: firm buy / add / trim / hold calls that are opinions, not validated strategies.

Clearly labelled as such everywhere. They still pass a deterministic gate (owner limits, protected index funds, cash only, no leverage,
a theme cap) and each approved call is stored as an immutable, hash-chained recommendation stamped BEFORE it is shown, with the entry
price and a benchmark price so the calls can be scored later. No orders are ever created: the owner places any trade himself.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .recommendations import Finding, record_findings
from .store import Store

TRACK = "JUDGMENT"
ACTIONS = ("BUY", "ADD", "TRIM", "HOLD")
CASH_FLOOR = Decimal("0.05")        # at least 5% of the account stays in cash after all calls
THEME_CAP = Decimal("0.30")         # a call may not push one theme above 30% of the account
BENCHMARK = "VTI"


@dataclass(frozen=True)
class Call:
    action: str
    symbol: str
    dollars: Decimal
    confidence: str            # low / medium / high
    horizon: str
    review_on: str
    rationale: str
    change_mind: str

    @staticmethod
    def parse(d: dict) -> "Call":
        return Call(d["action"].upper(), d["symbol"].upper(), Decimal(str(d.get("dollars", 0))), d["confidence"], d["horizon"],
                    d["review_on"], d["rationale"], d["change_mind"])


def _values(snapshot: dict, prices: dict[str, Decimal]) -> tuple[dict[str, Decimal], Decimal, Decimal]:
    cash = Decimal(str(snapshot["cash"]["USD"])) if isinstance(snapshot.get("cash"), dict) else Decimal("0")
    vals = {s: Decimal(str(h["quantity"])) * prices[s] for s, h in snapshot["holdings"].items()}
    return vals, cash, cash + sum(vals.values())


def gate(calls: list[Call], snapshot: dict, prices: dict[str, Decimal], themes: dict[str, str], max_weight: Decimal,
         protected: frozenset[str]) -> list[tuple[Call, list[str]]]:
    """Deterministic checks, nothing here can be overridden by the author of the calls. Returns (call, blocking reasons) per call."""
    vals, cash, total = _values(snapshot, prices)
    out: list[tuple[Call, list[str]]] = []
    spend, new_vals = Decimal("0"), dict(vals)
    for c in calls:
        why: list[str] = []
        if c.action not in ACTIONS:
            why.append(f"unknown action {c.action}")
        if not c.rationale.strip() or not c.change_mind.strip():
            why.append("a call needs a rationale and what would change my mind")
        if c.symbol not in prices:
            why.append("no price for this symbol: refusing to call on missing data")
        if c.action in ("BUY", "ADD"):
            if c.dollars <= 0:
                why.append("buy size must be positive")
            if c.action == "BUY" and c.symbol in snapshot["holdings"]:
                why.append("already owned: use ADD")
            if c.action == "ADD" and c.symbol not in snapshot["holdings"]:
                why.append("not owned: use BUY")
            new = new_vals.get(c.symbol, Decimal("0")) + c.dollars
            if new / total > max_weight:
                why.append(f"would take {c.symbol} to {new / total:.1%}, above the {max_weight:.0%} position limit")
            spend += c.dollars
            if cash - spend < CASH_FLOOR * total:
                why.append(f"cash would fall below the {CASH_FLOOR:.0%} floor (cash only, no leverage)")
            th = themes.get(c.symbol)
            if th and sum(v for s, v in new_vals.items() if themes.get(s) == th) / total + c.dollars / total > THEME_CAP:
                why.append(f"would push theme '{th}' above {THEME_CAP:.0%} of the account")
            if not why:
                new_vals[c.symbol] = new
        elif c.action == "TRIM":
            if c.symbol in protected:
                why.append(f"{c.symbol} is a protected index fund: never trimmed or sold")
            if c.symbol not in snapshot["holdings"]:
                why.append("not owned")
            elif c.dollars <= 0 or c.dollars > vals[c.symbol]:
                why.append("trim size must be positive and no more than the holding")
        elif c.action == "HOLD" and c.symbol not in snapshot["holdings"]:
            why.append("not owned")
        out.append((c, why))
    return out


def to_finding(c: Call, price: Decimal, bench: Decimal) -> Finding:
    verb = {"BUY": "BUY", "ADD": "ADD to", "TRIM": "TRIM", "HOLD": "HOLD"}[c.action]
    size = f" about ${c.dollars:,.0f}" if c.action != "HOLD" else ""
    return Finding(f"judgment_{c.action.lower()}", c.symbol, "info" if c.action == "HOLD" else "act",
                   f"JUDGMENT CALL (not a validated strategy) - {verb} {c.symbol}{size}: {c.rationale}",
                   {"track": TRACK, "action": c.action, "dollars": str(c.dollars), "entry_price": str(price), "benchmark": BENCHMARK,
                    "benchmark_price": str(bench), "confidence": c.confidence, "horizon": c.horizon, "review_on": c.review_on,
                    "change_mind": c.change_mind})


def record_calls(store: Store, account_id: str, snapshot_id: str, approved: list[Call], prices: dict[str, Decimal], now: datetime) -> list[str]:
    fs = [to_finding(c, prices[c.symbol], prices[BENCHMARK]) for c in approved]
    return record_findings(store, account_id, snapshot_id, fs, now, actor="judgment")


def score(store: Store, prices: dict[str, Decimal]) -> list[dict]:
    """Return of each recorded call since entry versus the benchmark since the same day (BUY/ADD: higher is better; TRIM: lower is better)."""
    rows = []
    for r in store.conn.execute("SELECT created_at, subject, kind, evidence_json FROM recommendations WHERE kind LIKE 'judgment_%' ORDER BY created_at"):
        ev = json.loads(r["evidence_json"])
        if r["subject"] not in prices or BENCHMARK not in prices:
            continue
        own = prices[r["subject"]] / Decimal(ev["entry_price"]) - 1
        bm = prices[BENCHMARK] / Decimal(ev["benchmark_price"]) - 1
        rows.append({"at": r["created_at"], "symbol": r["subject"], "action": ev["action"], "since_call": f"{own:.1%}",
                     "benchmark": f"{bm:.1%}", "vs_benchmark": f"{own - bm:+.1%}"})
    return rows
