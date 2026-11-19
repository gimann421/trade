"""Research pipeline for the growth strategy G1: register -> ingest history -> backtest train/validation (holdout stays sealed).

Deterministic and idempotent. Nothing here trades; it produces immutable, hash-stamped research records.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from .adapters.base import MarketDataAdapter
from .domain import AssetClass, CapabilityTier, Instrument
from .domain.models import Bar
from .errors import NexusError
from .ideas import G1_ID, UNIVERSE, buy_and_hold, g1_strategy, iid
from .ingestion import bars_known_at, ingest_daily_bars
from .research import BacktestConfig, get_hypothesis, register_hypothesis, run_backtest, run_experiment
from .store import Store

HISTORY_START = date(2021, 1, 1)
AUTHOR = "quant_lab"

G1_RECORD = {
    "title": "G1: trend-filtered momentum rotation over a broad liquid universe",
    "asset_universe": [iid(s) for s in UNIVERSE],
    "rationale": "Intermediate-term cross-sectional momentum is a widely documented, persistent effect; a 200-day trend filter "
                 "tries to avoid holding assets in downtrends and lets the portfolio sit in cash when few qualify.",
    "signal_definition": "Rank by 126-session return skipping the latest 5 sessions; eligible only if momentum > 0 and close above "
                         "its 200-session average. Hold the top 5 equal weight (19.8% each, 1% always in cash for costs), rest cash. Decide at the close of the first "
                         "session of each month; trade at the next open.",
    "holding_period": "about one month, long only, no leverage",
    "entry_exit_sizing_risk": "Equal weight, max 5 positions, monthly rebalance; positions drop out when no longer eligible.",
    "benchmark_and_alternatives": "SPY buy and hold; maintain current holdings; cash.",
    "data_sources": ["alpaca-data iex daily bars, adjusted"],
    "train_period": ["2021-11-01", "2024-01-01"],
    "validation_period": ["2024-01-01", "2025-07-01"],
    "holdout_period": ["2025-07-01", "2026-12-31"],
    "known_biases": ["survivorship: universe built from today's leaders", "IEX-only volumes", "short sample with one major regime",
                     "single hypothesis tried, parameters fixed before testing (no tuning)"],
    "capacity_notes": "Liquid ETFs and mega-caps; capacity not a constraint at personal scale.",
    "cost_assumptions": "7 bps per side adverse cost (slippage + half spread); cost sensitivity at 3x.",
    "failure_conditions": "Net CAGR, drawdown, Sharpe or trade count miss the pre-registered criteria on validation or holdout.",
    "success_criteria": {"min_cagr_net": 0.12, "max_drawdown": 0.30, "min_sharpe": 0.7, "min_trades": 40},
    "paper_plan": {"min_days": 60, "min_fills": 20},
}


def ensure_universe(store: Store) -> None:
    for s in UNIVERSE:
        if store.get_instrument(iid(s)) is None:
            store.register_instrument(Instrument(iid(s), {"alpaca": s}, AssetClass.EQUITY, "USD", "America/New_York",
                                                 capability_tier=CapabilityTier.R3))


def ingest_universe(store: Store, adapter: MarketDataAdapter, end: date, start: date = HISTORY_START) -> dict:
    ok, bad = [], {}
    for s in UNIVERSE:
        try:
            snap, rep = ingest_daily_bars(store, adapter, iid(s), start, end)
            if rep.ok:
                ok.append(s)
            else:
                bad[s] = rep.issues[:2]
        except Exception as exc:
            bad[s] = [type(exc).__name__]
    return {"ok": ok, "failed": bad}


def latest_snapshot_ids(store: Store, symbols: list[str]) -> list[str]:
    out = []
    for s in symbols:
        r = store.conn.execute("SELECT snapshot_id FROM data_snapshots d WHERE snapshot_id LIKE ? AND quality='ok' "
                               "ORDER BY ingested_at DESC LIMIT 1", (f"%:{iid(s)}:%",)).fetchone()
        if r:
            out.append(r[0])
    return out


def research_g1(store: Store, now: datetime, symbols: list[str]) -> dict:
    """Register G1 (once), run train and validation, and a buy-and-hold SPY baseline on the same windows. Holdout is not touched."""
    ver = store.conn.execute("SELECT MAX(version) FROM hypotheses WHERE hyp_id=?", (G1_ID,)).fetchone()[0]
    if ver is not None:
        cur = {k: v for k, v in get_hypothesis(store, G1_ID, ver).items() if k not in ("hyp_id", "version", "author")}
        if cur != json.loads(json.dumps(G1_RECORD)):
            ver = None                    # the registered text differs from this code: register a new immutable version
    ver = ver or register_hypothesis(store, G1_ID, AUTHOR, G1_RECORD, now)
    rec = get_hypothesis(store, G1_ID, ver)
    universe = [iid(s) for s in symbols]
    snaps = latest_snapshot_ids(store, [s for s in symbols])
    if len(snaps) != len(symbols):
        raise NexusError("not every instrument has an OK snapshot; refuse to test on a partial universe")
    cfg = BacktestConfig()
    out = {"hypothesis": f"{G1_ID} v{ver}", "segments": {}}
    from .research import evaluate_criteria
    from .ingestion import get_snapshot_bars
    allbars: dict[str, list[Bar]] = {}
    for sid in snaps:
        for b in get_snapshot_bars(store, sid):
            allbars.setdefault(b.instrument_id, []).append(b)
    for seg in ("train", "validation"):
        have = store.conn.execute("SELECT 1 FROM experiments WHERE hyp_id=? AND version=? AND segment=?", (G1_ID, ver, seg)).fetchone()
        if have:
            continue
        # the registered universe must be fully covered by the snapshots (partial runs are refused above)
        res = run_experiment(store, G1_ID, ver, seg, g1_strategy, snaps, cfg, now)
        start, end = rec[f"{seg}_period"]
        spy = run_backtest({iid("SPY"): allbars[iid("SPY")]}, buy_and_hold(iid("SPY")), start, end, cfg)
        costly = run_backtest(allbars, g1_strategy, start, end, BacktestConfig(cost_multiplier=3.0))
        out["segments"][seg] = {"result": {k: res[k] for k in ("cagr_net", "max_drawdown", "sharpe", "trades", "total_return", "turnover")},
                                "criteria_failed": evaluate_criteria(rec["success_criteria"], res),
                                "spy_buy_hold": {k: spy[k] for k in ("cagr_net", "max_drawdown", "sharpe")},
                                "cagr_at_3x_costs": costly["cagr_net"]}
    return out


def daily_growth(store: Store, adapter: MarketDataAdapter, now: datetime, fallback_marks=None, lookback_days: int = 520) -> dict:
    """The daily growth loop: observe -> validate -> (re)rank -> forward-test sleeve and shadow ideas. Simulated only."""
    from datetime import timedelta
    from . import sleeve
    ensure_universe(store)
    from datetime import timedelta as _td
    from .calendars import NyseCalendar
    end = NyseCalendar().last_completed_session(now, _td(minutes=60)) or now.date()
    ing = ingest_universe(store, adapter, end, end - timedelta(days=lookback_days))
    out = {"data_failed": ing["failed"], "sleeve": sleeve.run_sleeve(store, now, ing["ok"])}
    out["shadow_ideas"] = sleeve.shadow_ideas(store, now, ing["ok"], fallback_marks=fallback_marks)
    out["filled_after"] = sleeve.fill_pending(store, now)
    return out
