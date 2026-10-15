"""Score hypothesis 133 (same-weekday seasonality) of research/r13-novel-ideas-2026-10-15.md.

    PYTHONPATH=. python research/round13_weekday.py --universe all
    PYTHONPATH=. python research/round13_weekday.py --universe holdout
    PYTHONPATH=. python research/round13_weekday.py --finalize
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import bars_path, load_bars
from core.intraday import sample_tickers
from core.ledger import add_evidence, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import STOCK_DIR, load_member_panel, load_membership, members_on, month_end_members, FIRST_MONTH_END, LAST_MONTH_END
from research.round13_common import register, title_of
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import BAR, COSTS, WINDOWS, break_even_bps, cleaned, dirty_index, placebo
from research.round11_ideas import judge

OUT_DIR = ROOT / "backtests" / "round13_weekday"
RID = "weekday_seasonal_s"
MINIMUM = {"IS": 250, "OOS": 150}
FIRST_DECISION = "2016-12-30"
LOOKBACK, MIN_OBS, FRACTION = 20, 15, 0.1


def weekday_scores(close: pd.DataFrame) -> pd.DataFrame:
    logret = np.log(close).diff()
    excess = logret.sub(logret.mean(axis=1), axis=0)
    weekday = pd.Series(close.index.weekday, index=close.index)
    next_weekday = weekday.shift(-1)
    per_day = {}
    for w in range(5):
        rows = excess[weekday == w]
        per_day[w] = rows.rolling(LOOKBACK, min_periods=MIN_OBS).mean().reindex(close.index).ffill()
    out = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    for w in range(5):
        sel = next_weekday == w
        out.loc[sel] = per_day[w].loc[sel]
    return out


def generate_targets(close, scores, decisions, members_fn):
    strategy = pd.DataFrame(np.nan, close.index, close.columns)
    detail = []
    for date, cands in zip(decisions, members_fn(decisions)):
        priced = [t for t in sorted(cands) if t in close.columns and pd.notna(close.at[date, t])]
        row = scores.loc[date, priced].dropna() if priced else pd.Series(dtype=float)
        n = max(1, int(round(FRACTION * len(row)))) if len(row) else 0
        picks = sorted(row.sort_values(ascending=False, kind="stable").index[:n]) if n else []
        strategy.loc[date] = 0.0
        if picks:
            strategy.loc[date, picks] = 1.0 / len(picks)
        detail.append({"date": date, "priced": priced, "ranked": list(row.index), "picks": picks, "share": 1.0})
    return strategy, detail


def run(universe):
    fs = load_module("factor_scan_v1")
    membership = load_membership()
    sample = set(sample_tickers())
    have = {t for t in month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END) if bars_path(t, STOCK_DIR).exists()}
    wanted = sorted({"holdout": have - sample, "all": have}[universe])
    index = load_bars("VTI").index
    close = load_member_panel(wanted, "close").reindex(index)
    full = close.copy()
    full["BIL"] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    cols = list(full.columns)
    dirty = dirty_index(index)
    fs.FIRST_DECISION = FIRST_DECISION
    members_fn = lambda dates: members_on(membership, dates)
    monthly = index[month_ends(index)]
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    _, bench_targets, bench_detail = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, cols), monthly, membership, None)
    bench = {n: cleaned(simulate(close_ff, bench_targets, b), dirty) for n, b in COSTS.items()}
    first_hold = index[index.get_loc(bench_detail[0]["date"]) + 1]
    scores = weekday_scores(close).reindex(columns=cols)
    decisions = [d for d in index[index.searchsorted(pd.Timestamp(FIRST_DECISION)):][:-1]]
    targets, detail = generate_targets(full, scores, decisions, members_fn)
    runs = {n: cleaned(simulate(close_ff, targets, b), dirty) for n, b in COSTS.items()}
    held = holding_windows(detail, index)
    cells = {}
    for label, (start, end) in WINDOWS.items():
        _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
        stress_active = window_stats(runs["stress"], bench["stress"], first_hold, start, end)[2]["net_active"]
        _, pct = placebo(detail, close_ff, index, start, end, dirty)
        n = sum(in_window(first, start, end) for _, first, _ in held)
        extra = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
        gross = stats["net_active"] + extra * COSTS["primary"] / 1e4
        verdict, why = judge(label, n, MINIMUM, stats, pct, stress_active, None)
        cells[label] = {"verdict": verdict, "why": why, "decisions": n, "net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                        "placebo": pct, "gross_active": gross, "annual_turnover": stats["annual_turnover"],
                        "break_even_bps": break_even_bps(gross, extra), "stress_net_active": stress_active, "start": stats["start"], "end": stats["end"]}
        print(f"{RID} [{universe}, {len(wanted)} names] {label}: act {stats['net_active']:+.1%} IR {stats['information_ratio']:+.2f} pl {pct:.2f} "
              f"gross {gross:+.1%} turnover {stats['annual_turnover']:.0f}x 10bp {stress_active:+.1%} -> {verdict}", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"round13_weekday_{universe}_{stamp}.json"
    conn = connect()
    register(conn)
    hid = lookup(conn)[title_of(RID)]
    for w, c in cells.items():
        be = f"{c['break_even_bps']:.1f}" if c["break_even_bps"] is not None else "n/a"
        add_evidence(conn, hid, "backtest",
                     f"{RID} [{universe} universe, {len(wanted)} names] {w} {c['start']}..{c['end']}, 5 bps, daily rebalance: {c['decisions']} decisions, net active "
                     f"{c['net_active']:.2%}/yr (gross {c['gross_active']:.2%}), IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}, turnover "
                     f"{c['annual_turnover']:.0f}x/yr, break-even {be} bps; 10 bps {c['stress_net_active']:.2%}. {c['verdict']}: {'; '.join(c['why'])}",
                     c["verdict"], ref=str(path.relative_to(ROOT)))
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "universe": universe, "names": len(wanted), "cells": cells}, indent=1, default=str) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def finalize():
    out = {}
    for u in ("all", "holdout"):
        files = sorted(OUT_DIR.glob(f"round13_weekday_{u}_*.json"))
        out[u] = json.loads(files[-1].read_text())["cells"]
    ok = all(c["verdict"] == "supports" for u in out.values() for c in u.values())
    bad = any(c["verdict"] == "contradicts" for u in out.values() for c in u.values())
    conn = connect()
    hid = lookup(conn)[title_of(RID)]
    set_strategy(conn, hid, "round13_weekday.py")
    set_status(conn, hid, "supported" if ok else "rejected" if bad else "testing")
    conn.close()
    print(RID, "supported" if ok else "rejected" if bad else "testing")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--universe", choices=["all", "holdout"])
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.finalize:
        finalize()
    elif args.universe:
        run(args.universe)


if __name__ == "__main__":
    sys.exit(main())
