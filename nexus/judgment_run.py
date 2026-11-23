"""Glue for the judgment track: read the calls file and the owner snapshot, price everything, gate, record, return the approved calls."""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from .judgment import BENCHMARK, Call, gate, record_calls, score
from .quotes import yahoo_last_close
from .suggest import price_snapshot
from .timeutil import utcnow


def run_calls_file(snapshot_path: str, calls_path: str, adapter_factory: Callable, store, themes_path: str | None = None,
                   now: datetime | None = None) -> dict:
    snap = json.loads(Path(snapshot_path).read_text())
    themes = json.loads(Path(themes_path).read_text()) if themes_path else {}
    spec = json.loads(Path(calls_path).read_text())
    calls = [Call.parse(d) for d in spec["calls"]]
    syms = sorted({*snap["holdings"], *(c.symbol for c in calls), BENCHMARK})
    prices, notes = price_snapshot({"holdings": {s: {} for s in syms}}, adapter_factory(), now or utcnow(), {},
                                   lambda s: yahoo_last_close(s))
    lim = store.config.risk_limits.get("owner_limits", {})
    max_w = Decimal(str(lim.get("max_position_weight") or "0.10"))
    protected = frozenset(lim.get("protected_from_sales") or ["VTI", "VXUS", "RSP"])
    checked = gate(calls, snap, prices, themes, max_w, protected)
    approved = [c for c, why in checked if not why]
    acct = store.conn.execute("SELECT account_id FROM ledger_accounts WHERE kind='ACTUAL' ORDER BY created_at DESC LIMIT 1").fetchone()
    sid = store.conn.execute("SELECT snapshot_id FROM portfolio_snapshots WHERE account_id=? ORDER BY as_of DESC, rowid DESC LIMIT 1", (acct[0],)).fetchone()
    stamp = now or utcnow()                                   # taken after pricing: the record is locked before the call is shown
    new = record_calls(store, acct[0], sid[0], approved, prices, stamp)
    return {"recorded": len(new), "approved": [{"action": c.action, "symbol": c.symbol, "dollars": str(c.dollars), "price": str(prices[c.symbol]),
                                                "confidence": c.confidence, "horizon": c.horizon, "review_on": c.review_on,
                                                "rationale": c.rationale, "change_mind": c.change_mind} for c in approved],
            "blocked": [{"symbol": c.symbol, "action": c.action, "why": why} for c, why in checked if why],
            "price_notes": notes, "scores": score(store, prices)}
