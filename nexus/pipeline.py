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
from .ideas import G1_ID, G2_ID, UNIVERSE, buy_and_hold, g1_strategy, g2_strategy, iid
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
        # the snapshot with the longest history (research needs the full window, not the short daily-refresh ones)
        r = store.conn.execute("SELECT d.snapshot_id FROM data_snapshots d WHERE d.snapshot_id LIKE ? AND d.quality='ok' "
                               "ORDER BY (SELECT MIN(session_date) FROM bars b WHERE b.snapshot_id=d.snapshot_id), d.ingested_at DESC LIMIT 1",
                               (f"%:{iid(s)}:%",)).fetchone()
        if r:
            out.append(r[0])
    return out


def research_strategy(store: Store, now: datetime, symbols: list[str], hyp_id: str, record: dict, strategy) -> dict:
    """Register G1 (once), run train and validation, and a buy-and-hold SPY baseline on the same windows. Holdout is not touched."""
    ver = store.conn.execute("SELECT MAX(version) FROM hypotheses WHERE hyp_id=?", (hyp_id,)).fetchone()[0]
    if ver is not None:
        cur = {k: v for k, v in get_hypothesis(store, hyp_id, ver).items() if k not in ("hyp_id", "version", "author")}
        if cur != json.loads(json.dumps(record)):
            ver = None                    # the registered text differs from this code: register a new immutable version
    ver = ver or register_hypothesis(store, hyp_id, AUTHOR, record, now)
    rec = get_hypothesis(store, hyp_id, ver)
    universe = [iid(s) for s in symbols]
    snaps = latest_snapshot_ids(store, [s for s in symbols])
    if len(snaps) != len(symbols):
        raise NexusError("not every instrument has an OK snapshot; refuse to test on a partial universe")
    cfg = BacktestConfig()
    out = {"hypothesis": f"{hyp_id} v{ver}", "segments": {}}
    from .research import evaluate_criteria
    from .ingestion import get_snapshot_bars
    allbars: dict[str, list[Bar]] = {}
    for sid in snaps:
        for b in get_snapshot_bars(store, sid):
            allbars.setdefault(b.instrument_id, []).append(b)
    for seg in ("train", "validation"):
        have = store.conn.execute("SELECT 1 FROM experiments WHERE hyp_id=? AND version=? AND segment=?", (hyp_id, ver, seg)).fetchone()
        if have:
            continue
        # the registered universe must be fully covered by the snapshots (partial runs are refused above)
        res = run_experiment(store, hyp_id, ver, seg, strategy, snaps, cfg, now)
        start, end = rec[f"{seg}_period"]
        spy = run_backtest({iid("SPY"): allbars[iid("SPY")]}, buy_and_hold(iid("SPY")), start, end, cfg)
        costly = run_backtest(allbars, strategy, start, end, BacktestConfig(cost_multiplier=3.0))
        out["segments"][seg] = {"result": {k: res[k] for k in ("cagr_net", "max_drawdown", "sharpe", "trades", "total_return", "turnover")},
                                "criteria_failed": evaluate_criteria(rec["success_criteria"], res),
                                "spy_buy_hold": {k: spy[k] for k in ("cagr_net", "max_drawdown", "sharpe")},
                                "cagr_at_3x_costs": costly["cagr_net"]}
    return out




def research_g1(store: Store, now: datetime, symbols: list[str]) -> dict:
    return research_strategy(store, now, symbols, G1_ID, G1_RECORD, g1_strategy)


G2_RECORD = {
    **G1_RECORD,
    "title": "G2: low-volatility leaders inside an uptrend",
    "rationale": "The low-volatility anomaly (Frazzini and Pedersen; Ang et al.): calmer assets have earned risk-adjusted returns at least as good "
                 "as volatile ones, because many investors overpay for exciting names. Restricting to assets in an uptrend avoids calm decliners. "
                 "A different premise from G1 (momentum) and aimed at the drawdown and Sharpe criteria G1 narrowly missed - chosen before looking at any G2 result.",
    "signal_definition": "Eligible: close above its 200-session average AND positive 126-session return. Rank eligible assets by lowest realized daily "
                         "volatility over 126 sessions; hold the 8 calmest, equal weight (12.4% each, 1% always in cash), rest cash. Decide at the close of the "
                         "first session of each month; trade at the next open.",
    "entry_exit_sizing_risk": "Equal weight, max 8 positions, monthly rebalance; positions drop out when ineligible.",
    "known_biases": ["survivorship: universe built from today's leaders", "IEX-only volumes", "short sample with one major regime",
                     "second hypothesis tried on the same universe and periods (multiple-testing: G1 and G2); parameters fixed before testing, no tuning",
                     "same pass bar as G1, deliberately not loosened"],
}


def research_g2(store: Store, now: datetime, symbols: list[str]) -> dict:
    return research_strategy(store, now, symbols, G2_ID, G2_RECORD, g2_strategy)


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


# ---------------- long-history (2004+) ETF research ----------------
LONG_DIR = "data/long"          # Yahoo adjusted daily bars from the repo's own core.longdata (gitignored); ETFs only, no delisted names
LONG_UNIVERSE = ("SPY QQQ IWM IWB IWD IWF VTI XLB XLE XLF XLI XLK XLP XLU XLV XLY EFA EEM VEA VNQ GLD DBC "
                 "TLT IEF IEI TLH LQD SHY AGG HYG EDV SPTL ZROZ VGIT VGLT").split()
LONG_SOURCE = "yahoo-long"


def load_long_bars(symbol: str, directory: str = LONG_DIR) -> list[Bar]:
    import csv
    with open(f"{directory}/{symbol}_1Day.csv", newline="", encoding="utf-8") as f:
        return [Bar(iid(symbol), r["date"], float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"]))
                for r in csv.DictReader(f)]


def ingest_long(store: Store, directory: str = LONG_DIR, start: date = date(2003, 1, 2)) -> dict:
    """Ingest the long ETF files through the same quality gates as live data. Single source (no stitching)."""
    from .adapters.fixture import FixtureAdapter
    from .timeutil import utcnow
    ok, bad = [], {}
    for sym in LONG_UNIVERSE:
        if store.get_instrument(iid(sym)) is None:
            store.register_instrument(Instrument(iid(sym), {"yahoo": sym}, AssetClass.EQUITY, "USD", "America/New_York",
                                                 capability_tier=CapabilityTier.R3))
        bars = [b for b in load_long_bars(sym, directory) if b.session_date >= start.isoformat()]
        try:
            _, rep = ingest_daily_bars(store, FixtureAdapter(bars, source=LONG_SOURCE, as_of=utcnow()), iid(sym),
                                       date.fromisoformat(bars[0].session_date), date.fromisoformat(bars[-1].session_date))
            (ok.append(sym) if rep.ok else bad.__setitem__(sym, rep.issues[:2]))
        except Exception as exc:
            bad[sym] = [type(exc).__name__ + ": " + str(exc)[:80]]
    return {"ok": ok, "failed": bad}


LONG_PERIODS = {"train_period": ["2004-01-01", "2012-01-01"], "validation_period": ["2012-01-01", "2018-01-01"],
                "holdout_period": ["2018-01-01", "2026-12-31"]}
LONG_BIAS_NOTE = ("ETF-only universe from the repo's Yahoo files, 2003 onward, single source (no stitching); funds that launched later join when "
                  "they exist, but ETFs that closed are absent (mild survivorship). Earlier versions of this hypothesis were already run on "
                  "2021-2026 Alpaca data and failed; the 2018-2026 'holdout' therefore overlaps years the author has already seen, so only the "
                  "forward test is clean. Candidates tried so far: G1 v2, G2 v1 (2021+), G1 v3, G2 v2 (long history).")


def long_record(base: dict) -> dict:
    return {**base, **LONG_PERIODS, "asset_universe": [iid(s) for s in LONG_UNIVERSE],
            "data_sources": ["yahoo daily bars via core.longdata (adjusted), 2003 onward"],
            "known_biases": [LONG_BIAS_NOTE, "pass bar identical to the 2021+ versions, deliberately not loosened",
                             "parameters fixed before testing, no tuning"]}
