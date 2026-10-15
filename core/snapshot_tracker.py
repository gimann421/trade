"""Forward shadow record for the 15:45-snapshot stock rules of round 9 (strategies/short_horizon_v2.py).

Every `hold` sessions (2 or 3) from the rule's start date, the rule ranks the priced point-in-time S&P 500 members on the
15:45 price of that day (the close of the 15:30-15:45 bar) against official closes, picks the names, and the
shadow portfolio is assumed filled at that session's official close. Each decision is written once to
paper/<rule>/decisions/<date>.json with the 15:45 prices it used; later runs reuse those files and only fetch
snapshots for new decision dates, so the record cannot drift. nav.csv is rebuilt from the decision files and
daily closes (5 bps on turnover; benchmark = equal weight of the members priced on both days of each interval,
rebalanced daily, no cost). Nothing here ever sends an order.

Limit: the daily runner executes after the close and reads the 15:45 bar from history, so the file proves what
the rule would have picked from the 15:45 price, not that it was committed before the 15:50 order cut-off.
"""

import json
from datetime import timezone

import numpy as np
import pandas as pd

from core.config import ROOT
from core.market_calendar import trading_days
from core.paper_runner import DataNotReady, _read_json, _write_json, fetch_closes, load_module
from core.universe import members_on

COST_BPS = 5.0
LOOKBACK_DAYS = 14
SNAPSHOT_MINUTE = 15 * 60 + 30     # the bar that starts at 15:30 closes at 15:45


def decision_sessions(start, end, hold: int = 2) -> list[pd.Timestamp]:
    days = trading_days(pd.Timestamp(start), pd.Timestamp(end))
    return list(days[::hold]) if len(days) and days[0] == pd.Timestamp(start) else []


def find_rule(strategy_rule: str):
    """The rule dict and its module: short_horizon_v2 first (the original shadow rule), then short_horizon_v3."""
    for name in ("short_horizon_v2", "short_horizon_v3"):
        module = load_module(name)
        rule = next((r for r in module.RULES if r["id"] == strategy_rule), None)
        if rule is not None:
            return rule, module
    return None, None


def fetch_snapshot(symbols, day, client=None, batch: int = 100, feed=None) -> pd.Series:
    """Price at 15:45 New York time on `day` for each symbol that has a 15:30-15:45 bar (adjustment ALL)."""
    from alpaca.data.enums import Adjustment
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    from core.config import load_paper_keys
    if client is None:
        keys = load_paper_keys()
        client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    day = pd.Timestamp(day)
    start = (day + pd.Timedelta(hours=12)).to_pydatetime().replace(tzinfo=timezone.utc)
    end = (day + pd.Timedelta(hours=23)).to_pydatetime().replace(tzinfo=timezone.utc)
    out = {}
    symbols = sorted(set(symbols))
    for i in range(0, len(symbols), batch):
        request = StockBarsRequest(symbol_or_symbols=symbols[i:i + batch], timeframe=TimeFrame(15, TimeFrameUnit.Minute),
                                   start=start, end=end, adjustment=Adjustment.ALL, feed=feed)
        df = client.get_stock_bars(request).df
        if df.empty:
            continue
        ts = df.index.get_level_values("timestamp").tz_convert("America/New_York")
        minutes = ts.hour * 60 + ts.minute
        keep = df[(minutes == SNAPSHOT_MINUTE) & (ts.date == day.date())]
        for (sym, _), close in keep["close"].items():
            out[sym] = float(close)
    return pd.Series(out, dtype=float)


def run_snapshot_rule(cfg: dict, session: pd.Timestamp, membership: pd.Series, out_dir, fetch_closes_fn=fetch_closes,
                      fetch_snapshot_fn=fetch_snapshot) -> dict:
    rule, sh = find_rule(cfg["strategy_rule"])
    if rule is None or rule["signal"] != "rev5" or rule["kind"] != "band":
        raise ValueError(f"{cfg['rule']}: the snapshot tracker supports the rev5 band rules only")
    start = pd.Timestamp(cfg["start"])
    status = {"rule": cfg["rule"], "kind": "snapshot", "strategy_rule": cfg["strategy_rule"], "asof": str(session.date()),
              "start": str(start.date())}
    decisions = decision_sessions(start, session, rule["hold"])
    if not decisions:
        status["state"] = "waiting"
        _write_json(out_dir, "status.json", status)
        return status

    members = sorted(frozenset().union(*members_on(membership, decisions)))
    closes = fetch_closes_fn(members, start - pd.Timedelta(days=LOOKBACK_DAYS), session)
    index = closes.dropna(how="all").index
    if index[-1] < session:
        raise DataNotReady(f"latest bar is {index[-1].date()}, but the last completed session is {session.date()}")
    closes = closes.reindex(index)

    held, picks_by_date, changed = [], {}, []
    for date in decisions:
        if date not in index:
            raise DataNotReady(f"no bar for decision date {date.date()}")
        stored = _read_json(out_dir, f"decisions/{date.date()}.json")
        priced = [t for t in sorted(members_on(membership, [date])[0]) if t in closes.columns and pd.notna(closes.at[date, t])]
        if stored is not None:
            snap = pd.Series(stored["snapshot_1545"], dtype=float)
        else:
            snap = fetch_snapshot_fn(priced, date)
            if snap.empty:
                raise DataNotReady(f"no 15:30 bars for {date.date()}")
        pos = index.get_loc(date)
        if pos < 5:
            raise DataNotReady("not enough history for the 5-day signal")
        base = closes.iloc[pos - 5]
        row = -(snap.reindex(priced) / base.reindex(priced) - 1)
        row = row.dropna()
        picks = sh.select(rule, row, held)
        record = {"decision_date": str(date.date()), "rule": cfg["rule"], "members": len(members_on(membership, [date])[0]),
                  "priced": len(priced), "ranked": len(row), "picks": picks,
                  "weight_each": 1.0 / len(picks) if picks else 0.0,
                  "snapshot_1545": {t: float(snap[t]) for t in sorted(snap.index)},
                  "closes": {t: float(closes.at[date, t]) for t in picks}}
        if stored is None:
            _write_json(out_dir, f"decisions/{date.date()}.json", record)
        elif sorted(stored["picks"]) != sorted(picks):
            changed.append({"decision_date": record["decision_date"], "stored_only": sorted(set(stored["picks"]) - set(picks)),
                            "recomputed_only": sorted(set(picks) - set(stored["picks"]))})
            picks = stored["picks"]
        held = picks
        picks_by_date[date] = picks

    close_ff = closes.ffill()
    returns = close_ff.pct_change(fill_method=None)
    initial = float(cfg.get("initial_cash", 100_000))
    nav, bench, weights = initial, initial, {}
    rows = []
    first = decisions[0]
    drifted = pd.Series(dtype=float)
    for day in index[index.get_loc(first) + 1:]:
        prev = index[index.get_loc(day) - 1]
        if prev in picks_by_date:
            target = pd.Series(1.0 / len(picks_by_date[prev]), picks_by_date[prev]) if picks_by_date[prev] else pd.Series(dtype=float)
            traded = target.sub(drifted, fill_value=0.0).abs().sum()
            nav *= 1 - traded * COST_BPS / 10_000
            weights = target
        r = returns.loc[day]
        gross = float((weights * r.reindex(weights.index).fillna(0.0)).sum()) if len(weights) else 0.0
        nav *= 1 + gross
        drifted = (weights * (1 + r.reindex(weights.index).fillna(0.0)) / (1 + gross)) if len(weights) else weights
        priced_both = [t for t in members_on(membership, [prev])[0] if t in returns.columns and pd.notna(r.get(t))]
        bench *= 1 + float(r[priced_both].mean()) if priced_both else 1.0
        rows.append({"date": day, "nav": nav, "benchmark_nav": bench, "invested": float(weights.sum()) if len(weights) else 0.0})
    navdf = pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(columns=["nav", "benchmark_nav", "invested"])
    last = decisions[-1]
    status |= {"state": "running" if rows else "waiting_for_first_interval", "first_decision": str(first.date()),
               "last_decision": str(last.date()), "decisions": len(decisions), "holdings": picks_by_date[last],
               "decisions_changed_since_recorded": changed}
    if rows:
        status |= {"nav": float(navdf["nav"].iloc[-1]), "benchmark_nav": float(navdf["benchmark_nav"].iloc[-1]),
                   "excess_return": float(navdf["nav"].iloc[-1] / navdf["benchmark_nav"].iloc[-1] - 1),
                   "total_return": float(navdf["nav"].iloc[-1] / initial - 1)}
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            navdf.to_csv(out_dir / "nav.csv", index_label="date")
    _write_json(out_dir, "status.json", status)
    return status
