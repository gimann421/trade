"""Test 3 of round 14: SPY on FOMC statement days and employment-report days only.

    PYTHONPATH=. python research/round14_announce.py --register
    PYTHONPATH=. python research/round14_announce.py
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, connect, set_status
from research.round14_common import register, title_of
from research.round14_data import employment_dates, fomc_dates
from research.round6_scan import lookup

OUT_DIR = ROOT / "backtests" / "round14_announce"
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", "2025-09-30")}
COST_BPS_ROUND_TRIP = 2.0
BAR = {"mean_bps": 8.0, "t": 1.65, "gap_bps": 6.0, "placebo": 0.95}
DRAWS, SEED = 1000, 0


def stats(ex, days, lo, hi):
    window = ex.loc[lo:hi]
    ann = window[window.index.isin(days)]
    other = window[~window.index.isin(days)]
    mean_gross = float(ann.mean() * 1e4)
    mean_net = mean_gross - COST_BPS_ROUND_TRIP
    t = float(ann.mean() / (ann.std(ddof=1) / np.sqrt(len(ann))))
    rng = np.random.default_rng(SEED)
    pool = window.to_numpy()
    draws = np.array([pool[rng.choice(len(pool), len(ann), replace=False)].mean() for _ in range(DRAWS)])
    return {"days": int(len(ann)), "mean_bps_net": mean_net, "mean_bps_gross": mean_gross, "t": t,
            "other_days_mean_bps": float(other.mean() * 1e4), "gap_bps": mean_net - float(other.mean() * 1e4),
            "placebo": float((draws < ann.mean()).mean())}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    conn = connect()
    ids = register(conn)
    if args.register:
        print(f"registered {ids}")
        return
    spy, bil = load_bars("SPY")["close"], load_bars("BIL")["close"]
    ex = (spy.pct_change() - bil.pct_change().reindex(spy.index)).dropna()
    ex.index = pd.to_datetime(ex.index)
    sets = {"both": sorted(set(fomc_dates()) | set(employment_dates())), "fomc": fomc_dates(), "employment": employment_dates()}
    cells, extra = {}, {}
    for label, (lo, hi) in WINDOWS.items():
        s = stats(ex, set(sets["both"]), lo, hi)
        fails = []
        if s["mean_bps_net"] < BAR["mean_bps"]:
            fails.append(f"mean {s['mean_bps_net']:.1f} bps < 8")
        if s["t"] < BAR["t"]:
            fails.append(f"t {s['t']:.2f} < 1.65")
        if s["gap_bps"] < BAR["gap_bps"]:
            fails.append(f"gap to other days {s['gap_bps']:.1f} bps < 6")
        if s["placebo"] < BAR["placebo"]:
            fails.append(f"placebo {s['placebo']:.3f} < 0.95")
        s["verdict"], s["why"] = ("contradicts", "; ".join(fails)) if fails else ("supports", "passes the bar")
        cells[label] = s
        extra[label] = {k: stats(ex, set(sets[k]), lo, hi) for k in ("fomc", "employment")}
        print(label, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()}))
        print("   report-only", {k: {a: round(b, 2) for a, b in v.items() if a in ("days", "mean_bps_net", "t", "placebo")} for k, v in extra[label].items()})
    status = "supported" if all(c["verdict"] == "supports" for c in cells.values()) else "rejected"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"announce_{stamp}.json"
    hid = lookup(conn)[title_of("announce_spy_s")]
    for w, c in cells.items():
        summary = (f"round14_announce announce_spy_s {w} {WINDOWS[w][0]}..{WINDOWS[w][1]}: {c['days']} FOMC and employment-report days, mean SPY excess "
                   f"return net of 2 bps {c['mean_bps_net']:.1f} bps/day (t {c['t']:.2f}), other days {c['other_days_mean_bps']:.1f} bps, gap "
                   f"{c['gap_bps']:.1f} bps, placebo {c['placebo']:.3f}. {c['verdict']}: {c['why']}")
        add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
    set_status(conn, hid, status)
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "bar": BAR, "status": status, "cells": cells,
                                "report_only": extra}, indent=1, default=str) + "\n")
    conn.close()
    print(status, f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
