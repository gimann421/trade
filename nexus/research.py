"""Hypothesis registry (spec 6.1) and a reproducible, point-in-time daily backtest engine (spec 7).

Rules enforced in code: a hypothesis must be fully specified and registered BEFORE any experiment; success
criteria are fixed at registration; the holdout can be evaluated exactly once per version; every experiment
records code commit, config hash and data snapshot ids, and its result is hashed so reruns can be compared.
"""
from __future__ import annotations

import json
import math
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .domain.enums import EventType
from .domain.models import Bar, canonical_json, content_hash
from .errors import NexusError, StaleOrInvalidDataError
from .ingestion import get_snapshot_bars, verify_snapshot
from .store import Store
from .timeutil import require_aware, to_iso

REQUIRED_FIELDS = (
    "title", "asset_universe", "rationale", "signal_definition", "holding_period", "entry_exit_sizing_risk",
    "benchmark_and_alternatives", "data_sources", "train_period", "validation_period", "holdout_period",
    "known_biases", "capacity_notes", "cost_assumptions", "failure_conditions", "success_criteria")
CRITERIA_KEYS = ("min_cagr_net", "max_drawdown", "min_sharpe", "min_trades")
Strategy = Callable[[dict[str, list[Bar]]], dict[str, float]]   # bars up to and including decision day -> target weights


def code_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip() + ("+dirty" if dirty.stdout.strip() else "")
    except Exception:
        pass
    return "unknown"


def register_hypothesis(store: Store, hyp_id: str, author: str, record: dict, now: datetime, version: int | None = None) -> int:
    missing = [f for f in REQUIRED_FIELDS if not record.get(f)]
    if missing:
        raise NexusError(f"hypothesis is not falsifiable/complete; missing: {', '.join(missing)}")
    crit = record["success_criteria"]
    if not isinstance(crit, dict) or any(k not in crit for k in CRITERIA_KEYS):
        raise NexusError(f"success_criteria must pre-register all of {CRITERIA_KEYS}")
    for per in ("train_period", "validation_period", "holdout_period"):
        a, b = record[per]
        if not a < b:
            raise NexusError(f"{per} must be [start, end) with start < end")
    tp, vp, hp = record["train_period"], record["validation_period"], record["holdout_period"]
    if not (tp[1] <= vp[0] and vp[1] <= hp[0]):
        raise NexusError("train, validation and holdout periods must be ordered and non-overlapping")
    nxt = store.conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM hypotheses WHERE hyp_id=?", (hyp_id,)).fetchone()[0]
    if version is not None and version != nxt:
        raise NexusError(f"next version for {hyp_id} is {nxt}")
    rec = {**record, "hyp_id": hyp_id, "version": nxt, "author": author}
    sha = content_hash(rec)
    ev = store.events.append(EventType.HYPOTHESIS_REGISTERED, "research", author, {"hyp_id": hyp_id, "version": nxt, "sha": sha},
                             occurred_at=now, idempotency_key=f"hyp:{hyp_id}:{nxt}")
    store.conn.execute("INSERT INTO hypotheses VALUES (?,?,?,?,?,?,?)",
                       (hyp_id, nxt, author, to_iso(require_aware(now)), canonical_json(rec), sha, ev.event_id))
    return nxt


def get_hypothesis(store: Store, hyp_id: str, version: int) -> dict:
    r = store.conn.execute("SELECT * FROM hypotheses WHERE hyp_id=? AND version=?", (hyp_id, version)).fetchone()
    if r is None:
        raise NexusError(f"hypothesis {hyp_id} v{version} is not registered; register before testing")
    if content_hash(json.loads(r["record_json"])) != r["record_sha"]:
        raise StaleOrInvalidDataError("hypothesis record fails its hash check")
    return json.loads(r["record_json"])


# ---------------- backtest engine ----------------
@dataclass(frozen=True)
class BacktestConfig:
    cost_bps: float = 7.0            # per-side adverse cost on traded notional (slippage + half spread)
    initial_equity: float = 100_000.0
    cost_multiplier: float = 1.0     # >1 for cost-sensitivity runs


def run_backtest(bars_by_inst: dict[str, list[Bar]], strategy: Strategy, start: str, end: str, cfg: BacktestConfig) -> dict:
    """Long-only target-weight daily backtest. Decision at the close of day t using bars <= t; trades at the OPEN of
    t+1 with adverse costs; equity marked at closes. Deterministic. [start, end) in ISO dates."""
    dates = sorted({b.session_date for bs in bars_by_inst.values() for b in bs})
    idx = {i: {b.session_date: b for b in bs} for i, bs in bars_by_inst.items()}
    for i, bs in bars_by_inst.items():
        if len({b.session_date for b in bs}) != len(bs):
            raise StaleOrInvalidDataError(f"duplicate bars for {i}")
    cash, pos = cfg.initial_equity, {i: 0.0 for i in bars_by_inst}
    eq_curve, turnover, cost_paid, trades = [], 0.0, 0.0, 0
    pending: dict[str, float] | None = None
    last_close = {i: None for i in bars_by_inst}
    for d in [x for x in dates if start <= x < end]:
        # 1) execute yesterday's decision at today's open
        if pending is not None:
            opens = {i: idx[i][d].open if d in idx[i] else None for i in bars_by_inst}
            nav_open = cash + sum(pos[i] * (opens[i] if opens[i] is not None else (last_close[i] or 0)) for i in pos)
            c_rate = cfg.cost_bps * cfg.cost_multiplier / 1e4
            plan = []
            for i, w in pending.items():
                if opens[i] is None:
                    continue                                         # no bar: cannot trade (no silent fill)
                want = (w * nav_open) / opens[i]
                if want > pos[i]:
                    want = (w * nav_open) / (opens[i] * (1 + c_rate))   # size buys so that cost fits inside the weight
                plan.append((i, want - pos[i], want))
            for i, delta, want in sorted(plan, key=lambda t: t[1]):      # sells first, then buys
                if abs(delta * opens[i]) < 1e-9:
                    continue
                px = opens[i] * (1 + c_rate * (1 if delta > 0 else -1))
                cash -= delta * px
                cost_paid += abs(delta) * opens[i] * c_rate
                turnover += abs(delta * opens[i]) / max(nav_open, 1e-9)
                trades += 1
                pos[i] = want
            if cash < -1e-6 * cfg.initial_equity:
                raise StaleOrInvalidDataError("backtest strategy implied leverage (weights sum above 1)")
            pending = None
        for i in bars_by_inst:
            if d in idx[i]:
                last_close[i] = idx[i][d].close
        nav = cash + sum(pos[i] * (last_close[i] or 0) for i in pos)
        eq_curve.append((d, nav))
        # 2) decide at today's close using only bars <= d
        hist = {i: [b for b in bs if b.session_date <= d] for i, bs in bars_by_inst.items()}
        w = strategy(hist)
        if any(x < 0 for x in w.values()) or sum(w.values()) > 1 + 1e-9 or set(w) - set(bars_by_inst):
            raise NexusError("strategy returned invalid weights (long-only, sum<=1, known instruments)")
        pending = {i: float(w.get(i, 0.0)) for i in bars_by_inst}
    return _metrics(eq_curve, turnover, cost_paid, trades, cfg)


def _metrics(curve: list[tuple[str, float]], turnover: float, cost_paid: float, trades: int, cfg: BacktestConfig) -> dict:
    if len(curve) < 3:
        raise StaleOrInvalidDataError("too few observations for metrics")
    navs = [n for _, n in curve]
    rets = [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs))]
    n = len(rets)
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    vol = math.sqrt(var) * math.sqrt(252)
    peak, mdd = navs[0], 0.0
    for v in navs:
        peak = max(peak, v)
        mdd = max(mdd, 1 - v / peak)
    years = n / 252
    cagr = (navs[-1] / navs[0]) ** (1 / years) - 1 if years > 0 and navs[0] > 0 and navs[-1] > 0 else -1.0
    down = [min(r, 0) for r in rets]
    dvol = math.sqrt(sum(x * x for x in down) / n) * math.sqrt(252)
    r = lambda x: round(x, 10)
    return {"observations": n, "start": curve[0][0], "end": curve[-1][0], "total_return": r(navs[-1] / navs[0] - 1),
            "cagr_net": r(cagr), "volatility": r(vol), "downside_volatility": r(dvol), "max_drawdown": r(mdd),
            "sharpe": r(mean * 252 / vol) if vol > 0 else 0.0, "sortino": r(mean * 252 / dvol) if dvol > 0 else 0.0,
            "turnover": r(turnover), "costs_paid": r(cost_paid), "trades": trades,
            "cost_multiplier": cfg.cost_multiplier}


def run_experiment(store: Store, hyp_id: str, version: int, segment: str, strategy: Strategy, snapshot_ids: list[str],
                   cfg: BacktestConfig, now: datetime) -> dict:
    """Run on one registered segment, reading only verified snapshots; persist an immutable, hash-stamped result."""
    h = get_hypothesis(store, hyp_id, version)
    if segment not in ("train", "validation", "holdout"):
        raise NexusError("segment must be train, validation or holdout")
    start, end = h[f"{segment}_period"]
    if segment == "holdout" and store.conn.execute("SELECT 1 FROM experiments WHERE hyp_id=? AND version=? AND segment='holdout'", (hyp_id, version)).fetchone():
        raise NexusError("the holdout has already been used for this hypothesis version; register a new version and a new holdout")
    bars: dict[str, list[Bar]] = {}
    for sid in snapshot_ids:
        verify_snapshot(store, sid)
        for b in get_snapshot_bars(store, sid):
            bars.setdefault(b.instrument_id, []).append(b)
    if not bars:
        raise StaleOrInvalidDataError("no data")
    universe = set(h["asset_universe"])
    if set(bars) - universe:
        raise NexusError("snapshots contain instruments outside the registered universe")
    result = run_backtest(bars, strategy, start, end, cfg)
    cfg_sha = content_hash(vars(cfg))
    result_sha = content_hash(result)
    eid = f"exp-{uuid.uuid4().hex[:12]}"
    store.conn.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (eid, hyp_id, version, segment, to_iso(require_aware(now)), code_commit(), cfg_sha,
                        json.dumps(sorted(snapshot_ids)), canonical_json(result), result_sha))
    store.events.append(EventType.EXPERIMENT_RECORDED, "research", "system",
                        {"exp_id": eid, "hyp_id": hyp_id, "version": version, "segment": segment, "result_sha": result_sha})
    return {"exp_id": eid, "result_sha": result_sha, **result}


def evaluate_criteria(criteria: dict, result: dict) -> list[str]:
    """Deterministic comparison of a result with the PRE-REGISTERED criteria. Returns failed checks (empty = pass)."""
    fails = []
    if result["cagr_net"] < criteria["min_cagr_net"]:
        fails.append(f"cagr_net {result['cagr_net']} < {criteria['min_cagr_net']}")
    if result["max_drawdown"] > criteria["max_drawdown"]:
        fails.append(f"max_drawdown {result['max_drawdown']} > {criteria['max_drawdown']}")
    if result["sharpe"] < criteria["min_sharpe"]:
        fails.append(f"sharpe {result['sharpe']} < {criteria['min_sharpe']}")
    if result["trades"] < criteria["min_trades"]:
        fails.append(f"trades {result['trades']} < {criteria['min_trades']}")
    return fails
