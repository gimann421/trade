"""Continuous strategy search: one pre-authored candidate per run, registered then tested on the long ETF history, then the Red Team.

The pass bar is the same fixed criteria every time and is never loosened. Each candidate registered raises the count the deflated-Sharpe
check discounts against. The loop can only ever reach "cleared the Red Team, needs independent review"; it cannot promote or advise.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from .candidates import CANDIDATES, Candidate
from .domain.models import Bar
from .ideas import iid
from .ingestion import get_snapshot_bars
from .pipeline import LONG_BIAS_NOTE, LONG_PERIODS, AUTHOR, ingest_long, latest_snapshot_ids, research_strategy
from .redteam import challenge
from .store import Store
from .timeutil import utcnow

LEDGER_DIR = "/mnt/project-files/nexus/search"
CRITERIA = {"min_cagr_net": 0.12, "max_drawdown": 0.30, "min_sharpe": 0.7, "min_trades": 40}      # fixed; identical for every candidate


def record_for(c: Candidate) -> dict:
    syms = c.symbols
    return {
        "title": c.title, "asset_universe": [iid(s) for s in syms], "rationale": c.rationale, "signal_definition": c.signal,
        "holding_period": "monthly rule (daily for the two daily rules), long only, no leverage",
        "entry_exit_sizing_risk": "Weights fixed by the rule, summing to at most 99% (1% cash buffer for costs).",
        "benchmark_and_alternatives": "SPY buy and hold; cash.",
        "data_sources": ["yahoo daily bars via core.longdata (adjusted), 2003 onward"],
        **LONG_PERIODS,
        "known_biases": [LONG_BIAS_NOTE, "authored in a batch before any candidate was tested; parameters fixed, no tuning",
                         "pass bar identical for every candidate, deliberately not loosened; deflated-Sharpe discounts for all registered tries"],
        "capacity_notes": "Liquid ETFs; capacity not a constraint at personal scale.",
        "cost_assumptions": "7 bps per side adverse cost; cost sensitivity at 3x.",
        "failure_conditions": "Net CAGR, drawdown, Sharpe or trade count miss the pre-registered criteria on train or validation; or any Red Team hard check fails.",
        "success_criteria": CRITERIA, "paper_plan": {"min_days": 60, "min_fills": 20},
    }


def _ledger_path(d: str) -> str:
    return os.path.join(d, "ledger.json")


def load_ledger(d: str = LEDGER_DIR) -> list[dict]:
    try:
        with open(_ledger_path(d), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _save(d: str, rows: list[dict]) -> None:
    os.makedirs(d, exist_ok=True)
    tmp = _ledger_path(d) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    os.replace(tmp, _ledger_path(d))


def next_candidate(done: set[str]) -> Candidate | None:
    return next((c for c in CANDIDATES if c.cid not in done), None)


def run_candidate(store: Store, c: Candidate, now: datetime) -> dict:
    res = research_strategy(store, now, list(c.symbols), c.cid, record_for(c), c.strategy)
    ver = int(res["hypothesis"].rsplit(" v", 1)[1])
    bars: dict[str, list[Bar]] = {}
    for sid in latest_snapshot_ids(store, list(c.symbols)):
        for b in get_snapshot_bars(store, sid):
            bars.setdefault(b.instrument_id, []).append(b)
    rt = challenge(store, c.cid, ver, bars, now, c.strategy, list(c.variants))
    seg = {}
    for name in ("train", "validation"):          # read back from the recorded experiments so a retried run still reports them
        r = store.conn.execute("SELECT result_json FROM experiments WHERE hyp_id=? AND version=? AND segment=? ORDER BY created_at DESC LIMIT 1",
                               (c.cid, ver, name)).fetchone()
        full = json.loads(r[0])
        seg[name] = {k: full[k] for k in ("cagr_net", "max_drawdown", "sharpe", "trades", "total_return", "turnover")}
    return {"cid": c.cid, "title": c.title, "version": ver, "verdict": rt["verdict"], "segments": seg,
            "failed_checks": [f["check"] for f in rt["findings"] if f["hard"] and not f["passed"]], "at": now.isoformat()}


def run_next(store: Store, now: datetime | None = None, ledger_dir: str = LEDGER_DIR, ingest: bool = True) -> dict:
    """Test the next untried candidate. Returns a summary; ``cleared`` is True only when no Red Team hard check failed."""
    rows = load_ledger(ledger_dir)
    c = next_candidate({r["cid"] for r in rows})
    if c is None:
        return {"status": "queue_empty", "tried": len(rows), "note": "write more pre-registered candidates before searching further"}
    if ingest:
        ingest_long(store)
    row = run_candidate(store, c, now or utcnow())
    row["cleared"] = row["verdict"] == "defer"
    rows.append(row)
    _save(ledger_dir, rows)
    return {"status": "tested", "tried": len(rows), "remaining": len(CANDIDATES) - len(rows), **row}


def digest(ledger_dir: str = LEDGER_DIR) -> dict:
    rows = load_ledger(ledger_dir)
    best = max(rows, key=lambda r: r["segments"].get("validation", {}).get("sharpe", -9), default=None)
    return {"tried": len(rows), "queued": len(CANDIDATES) - len(rows), "cleared": [r["cid"] for r in rows if r.get("cleared")],
            "best_validation_sharpe": None if best is None else {"cid": best["cid"], "sharpe": best["segments"]["validation"]["sharpe"]}}
