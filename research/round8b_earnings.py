"""Score the four earnings-drift rules of research/r8-short-horizon-2026-10-14.md, Part B (hypotheses 90-93).

    PYTHONPATH=. python research/round8b_earnings.py --register
    PYTHONPATH=. python research/round8b_earnings.py

Needs data/edgar/events.csv (python -m core.edgar) and the stock bars in data/sp500/.
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.edgar import load_events, reaction_sessions
from core.ledger import add_evidence, add_hypothesis, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on,
                           month_end_members)
from research.round5_verdicts import holding_windows, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import (BAR, COSTS, DIRTY, PLACEBO, WINDOWS, break_even_bps, cleaned, dirty_index,
                                           judge, weeks_to_confidence)

MEMO = "research/r8-short-horizon-2026-10-14.md"
MIN_EVENTS = {"IS": 200, "OOS": 100}
HYPOTHESES_BEFORE = 89
OUT_DIR = ROOT / "backtests" / "earnings_drift_v1"


def describe(rule: dict) -> str:
    return (f"Holding each S&P 500 name whose earnings-day abnormal return is at or above the {rule['q']}th percentile "
            f"of the previous year's events for {rule['hold']} sessions after the reaction close, equal weight, beats the "
            f"equal-weight set by >= 2.0%/yr net with information ratio >= 0.3, event placebo >= 0.95, and still "
            f"positive when filled a session late and at 10 bps, in both IS 2017-2022 and OOS 2023+.")


def register(conn, rules) -> dict:
    ids = lookup(conn)
    for rule in rules:
        title = f"Earnings drift v1: {rule['id']}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, describe(rule),
                                        rationale="Round-8 Part B: post-earnings-announcement drift; see the memo.",
                                        research_memo=MEMO, strategy="earnings_drift_v1.py")
    return {r["id"]: ids[f"Earnings drift v1: {r['id']}"] for r in rules}


def event_placebo(actual_returns: np.ndarray, pool: np.ndarray):
    """Percentile of the mean h-session abnormal return of the qualifying events among random draws of the same
    number of events from the pool."""
    rng = np.random.default_rng(PLACEBO["seed"])
    n = len(actual_returns)
    idx = np.argsort(rng.random((PLACEBO["n"], len(pool))), axis=1)[:, :n]
    draws = pool[idx].mean(axis=1)
    mean = float(actual_returns.mean())
    return mean, float((draws < mean).mean())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    fs, ed = load_module("factor_scan_v1"), load_module("earnings_drift_v1")
    conn = connect()
    ids = register(conn, ed.RULES)
    if args.register:
        print(f"{len(ids)} rules registered, ids {min(ids.values())}-{max(ids.values())}")
        return

    events = load_events()
    restricted = frozenset(events["symbol"].unique())
    membership = load_membership().map(lambda s: s & restricted)
    wanted = sorted(month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END))
    index = load_bars("VTI").index
    close = load_member_panel(wanted, "close").reindex(index)
    stocks = list(close.columns)
    close["BIL"] = load_bars("BIL")["close"].reindex(index)
    close_ff = close.ffill()
    columns = list(close.columns)
    dirty = dirty_index(index)
    fs.FIRST_DECISION = "2016-12-30"
    first_pos = index.searchsorted(pd.Timestamp(fs.FIRST_DECISION))

    # benchmark: equal weight of the restricted point-in-time members, monthly
    monthly = index[month_ends(index)]
    probe = {"id": "probe", "family": "stock", "signal": "none", "fraction": 0.1, "trend": False}
    _, bench_targets, bench_detail = fs.generate_targets(probe, close, pd.DataFrame(np.nan, index, columns), monthly, membership, None)
    bench = {name: cleaned(simulate(close_ff, bench_targets, bps), dirty) for name, bps in COSTS.items()}
    bench["late"] = cleaned(simulate(close_ff, bench_targets.shift(1), COSTS["primary"]), dirty)
    first_hold = index[index.get_loc(bench_detail[0]["date"]) + 1]

    # events -> reaction sessions, abnormal reaction, qualification
    events = events[events["symbol"].isin(stocks)].copy()
    local_day = events["acceptance_utc"].dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
    events = events[local_day >= index[0]]  # releases before the first bar have no reaction session in the data
    events["reaction"] = reaction_sessions(events["acceptance_utc"], index)
    events = events.dropna(subset=["reaction"]).drop_duplicates(["symbol", "reaction"])
    events = events[~events["reaction"].isin(dirty)]
    events["pos"] = index.get_indexer(events["reaction"])
    events["col"] = [stocks.index(s) for s in events["symbol"]]
    ret = close[stocks].pct_change(fill_method=None)
    market = ret.mean(axis=1)
    events["ar"] = ret.to_numpy()[events["pos"], events["col"]] - market.to_numpy()[events["pos"]]
    events = events.dropna(subset=["ar"]).sort_values(["pos", "symbol"]).reset_index(drop=True)
    member_on = [s in members_on(membership, [d])[0] for s, d in zip(events["symbol"], events["reaction"])]
    events["member"] = member_on
    market_cum = (1 + market.fillna(0.0)).cumprod().to_numpy()
    close_np = close_ff[stocks].to_numpy()

    results, stamp = {}, pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"earnings_drift_{stamp}.json"
    for rule in ed.RULES:
        qual = ed.qualifies(events["pos"].to_numpy(), events["ar"].to_numpy(), rule["q"])
        events["qual"] = qual & events["member"].to_numpy() & (events["pos"].to_numpy() > first_pos)
        events["h_ar"] = ed.hold_returns(close_np, market_cum, events["pos"].to_numpy(), events["col"].to_numpy(), rule["hold"])
        q_events = events[events["qual"]]
        active = ed.active_matrix((len(index), len(stocks)), q_events["pos"].to_numpy(), q_events["col"].to_numpy(), rule["hold"])
        targets = ed.targets_from_active(active, index, columns, first_pos)
        runs = {"primary": cleaned(simulate(close_ff, targets, COSTS["primary"]), dirty),
                "stress": cleaned(simulate(close_ff, targets, COSTS["stress"]), dirty),
                "late": cleaned(simulate(close_ff, targets.shift(1), COSTS["primary"]), dirty)}
        cells = {}
        dirty_pos = set(index.get_indexer(dirty))
        for label, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
            late_active = window_stats(runs["late"], bench["late"], first_hold, start, end)[2]["net_active"]
            stress_active = window_stats(runs["stress"], bench["stress"], first_hold, start, end)[2]["net_active"]
            lo = max(pd.Timestamp(start), first_hold)
            hi = pd.Timestamp(end) if end else index[-1]
            in_win = (events["reaction"] >= lo) & (events["reaction"] <= hi) & events["h_ar"].notna()
            touches_dirty = np.array([any(p + k in dirty_pos for k in range(rule["hold"] + 1)) for p in events["pos"]])
            usable = in_win & ~touches_dirty & (events["pos"].to_numpy() > first_pos)
            pool = events.loc[usable & events["member"], "h_ar"].to_numpy()
            actual = events.loc[usable & events["qual"], "h_ar"].to_numpy()
            n_qual = int((in_win & events["qual"]).sum())
            mean_h, pct = event_placebo(actual, pool) if len(actual) and len(pool) > len(actual) else (float("nan"), 0.0)
            extra_turnover = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
            gross_active = stats["net_active"] + extra_turnover * COSTS["primary"] / 1e4
            verdict, why, sensitive = judge(label, n_qual, stats, pct, late_active, stress_active, MIN_EVENTS)
            cells[label] = {"verdict": verdict, "why": why, "execution_sensitive": sensitive, "decisions": n_qual,
                            "net_active": stats["net_active"], "information_ratio": stats["information_ratio"], "placebo": pct,
                            "gross_active": gross_active, "annual_turnover": stats["annual_turnover"],
                            "break_even_bps": break_even_bps(gross_active, extra_turnover),
                            "delayed_net_active": late_active, "stress_net_active": stress_active,
                            "mean_h_abnormal_qualifiers": mean_h, "mean_h_abnormal_pool": float(np.nanmean(pool)) if len(pool) else None,
                            "mean_ar_qualifiers": float(events.loc[in_win & events["qual"], "ar"].mean()),
                            "events_in_window": int(in_win.sum()), "beta": stats["beta_to_benchmark"],
                            "start": stats["start"], "end": stats["end"]}
        whole = window_stats(runs["primary"], bench["primary"], first_hold, "2016-01-01", None)[2]
        status = "supported" if all(c["verdict"] == "supports" for c in cells.values()) else \
            "rejected" if any(c["verdict"] == "contradicts" for c in cells.values()) else "testing"
        results[rule["id"]] = {"rule": rule, "status": status, "cells": cells, "information_ratio_all": whole["information_ratio"],
                               "net_active_all": whole["net_active"], "weeks_to_confidence": weeks_to_confidence(whole["information_ratio"])}
        print(f"{rule['id']:14s} " + "  ".join(
            f"{w} n {c['decisions']:4d} act {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} gross "
            f"{c['gross_active']:+6.1%} late {c['delayed_net_active']:+6.1%} 10bp {c['stress_net_active']:+6.1%} h-AR "
            f"{c['mean_h_abnormal_qualifiers']:+.2%} vs pool {c['mean_h_abnormal_pool'] if c['mean_h_abnormal_pool'] is None else round(c['mean_h_abnormal_pool'], 4)}"
            for w, c in cells.items()) + f"  -> {status}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger_ids = lookup(conn)
    for rid, res in results.items():
        hid = ledger_ids[f"Earnings drift v1: {rid}"]
        for w, c in res["cells"].items():
            tag = " [execution-sensitive]" if c["execution_sensitive"] else ""
            be = f"{c['break_even_bps']:.1f}" if c["break_even_bps"] is not None else "n/a"
            summary = (f"earnings_drift_v1 {rid} {w} {c['start']}..{c['end']}, 5 bps: {c['decisions']} qualifying events, net active "
                       f"{c['net_active']:.2%}/yr (gross {c['gross_active']:.2%}), IR {c['information_ratio']:.2f}, event placebo "
                       f"{c['placebo']:.3f}, turnover {c['annual_turnover']:.0f}x/yr, break-even {be} bps; delayed fill "
                       f"{c['delayed_net_active']:.2%}, 10 bps {c['stress_net_active']:.2%}. {c['verdict']}{tag}: {'; '.join(c['why'])}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
        set_strategy(conn, hid, "earnings_drift_v1.py")
        set_status(conn, hid, res["status"])
    passing = [r for r, v in results.items() if v["status"] == "supported"]
    note = (f"Round-8 Part B earnings drift: {len(results)} rules, {len(passing)} supported ({', '.join(passing) or 'none'}). "
            f"Hypotheses tested so far: {HYPOTHESES_BEFORE + len(results)}.")
    for rid in passing:
        add_evidence(conn, ledger_ids[f"Earnings drift v1: {rid}"], "note", note, "supports")
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "bar": BAR, "costs": COSTS, "events_total": len(events),
                                "events_member": int(events["member"].sum()), "note": note, "results": results}, indent=1, default=str) + "\n")
    print(note)
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
