"""Test 1 of round 14: reversal rules read at 3:30 and filled at 3:45 versus the same signal filled at the close.

    PYTHONPATH=. python research/round14_fills.py --register
    PYTHONPATH=. python research/round14_fills.py --check
    PYTHONPATH=. python research/round14_fills.py
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
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round14_common import MEMO, block_bootstrap_positive, register, title_of
from research.round5_verdicts import holding_windows, in_window
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import WINDOWS, cleaned, dirty_index
from research.round9_executable import load_inputs

OUT_DIR = ROOT / "backtests" / "round14_fills"
PARENTS = {"rev5_h2_band_f45_s": "rev5_h2_band_s", "rev5_h3_band40_f45_s": "rev5_h3_band40_s"}
MIN_DECISIONS = {2: {"IS": 250, "OOS": 150}, 3: {"IS": 160, "OOS": 100}}
BAR_DIFF = 0.01
BOOT_MIN = 0.80
CLOSE_BPS, FILL_BPS = 5.0, 7.0
SWEEP = (5.0, 7.0, 9.0, 11.0)


def active(run, bench, first_hold, start, end):
    lo = max(pd.Timestamp(start), first_hold)
    return (run["returns"] - bench["returns"]).loc[lo:end].dropna()


def annual(series):
    return float(series.mean() * 252)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry", action="store_true", help="print results, write nothing")
    args = parser.parse_args()
    conn = connect()
    ids = register(conn)
    if args.register:
        print(f"registered {ids}")
        return
    fs, sh = load_module("factor_scan_v1"), load_module("short_horizon_v3")
    membership, index, close, open_, snaps, report = load_inputs(sh)
    print("data check:", json.dumps(report))
    if args.check:
        return
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    p45 = snaps["p1545"].copy()
    p45[sh.CASH] = full[sh.CASH]
    p45_ff = p45.ffill()
    dirty = dirty_index(index)
    fs.FIRST_DECISION = sh.FIRST_DECISION
    members_fn = lambda dates: members_on(membership, dates)
    monthly = index[month_ends(index)]
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    none_scores = pd.DataFrame(np.nan, index, full.columns)
    _, bench_targets, bench_detail = fs.generate_targets(probe, full, none_scores, monthly, membership, None)
    first_hold = index[index.get_loc(bench_detail[0]["date"]) + 1]
    bench_close = cleaned(simulate(close_ff, bench_targets, CLOSE_BPS), dirty)
    bench_fill = {c: cleaned(simulate(p45_ff, bench_targets, c), dirty) for c in SWEEP}

    def scores_for(signal, price):
        s = sh.score_matrix(signal, open_, close, None if price == "close" else snaps[price])
        s[sh.CASH] = np.nan
        return s

    results, stamp = {}, pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    for rid, parent_id in PARENTS.items():
        rule = next(r for r in sh.RULES if r["id"] == parent_id)
        decisions = sh.decision_dates(index, rule["hold"])
        t30, d30 = sh.generate_targets(rule, full, scores_for(rule["signal"], "p1530"), None, decisions, members_fn)
        t45, _ = sh.generate_targets(rule, full, scores_for(rule["signal"], "p1545"), None, decisions, members_fn)
        parent = cleaned(simulate(close_ff, t45, CLOSE_BPS), dirty)
        control = cleaned(simulate(close_ff, t30, CLOSE_BPS), dirty)
        fills = {c: cleaned(simulate(p45_ff, t30, c), dirty) for c in SWEEP}
        upper = cleaned(simulate(p45_ff, t45, FILL_BPS), dirty)
        windows = holding_windows(d30, index)
        cells = {}
        for label, (start, end) in WINDOWS.items():
            a_fill = {c: active(fills[c], bench_fill[c], first_hold, start, end) for c in SWEEP}
            a_ctrl = active(control, bench_close, first_hold, start, end)
            a_par = active(parent, bench_close, first_hold, start, end)
            a_up = active(upper, bench_fill[FILL_BPS], first_hold, start, end)
            diff = (a_fill[FILL_BPS] - a_ctrl).dropna()
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            lo = max(pd.Timestamp(start), first_hold)
            years = len(a_ctrl) / 252
            turnover = float(fills[FILL_BPS]["traded"].loc[lo:end].sum() / years)
            boot = block_bootstrap_positive(diff)
            need = MIN_DECISIONS[rule["hold"]][label]
            fails = []
            if n < need:
                verdict, why = "inconclusive", [f"only {n} decisions (need {need})"]
            else:
                if annual(diff) < BAR_DIFF:
                    fails.append(f"fill-time gain {annual(diff):.2%}/yr < 1.0%")
                if annual(a_fill[FILL_BPS]) <= 0:
                    fails.append(f"own net active {annual(a_fill[FILL_BPS]):.2%} not above 0")
                if not boot >= BOOT_MIN:
                    fails.append(f"bootstrap P(gain>0) {boot:.2f} < 0.80")
                verdict, why = ("contradicts", fails) if fails else ("supports", ["passes the bar"])
            cells[label] = {"verdict": verdict, "why": why, "decisions": n, "start": str(lo.date()),
                            "net_active_f45_7bps": annual(a_fill[7.0]), "net_active_by_cost": {str(c): annual(a_fill[c]) for c in SWEEP},
                            "net_active_control_close": annual(a_ctrl), "net_active_parent_3_45_close": annual(a_par),
                            "net_active_upper_bound_sig45_fill45": annual(a_up), "gain_vs_control": annual(diff),
                            "bootstrap_p": boot, "turnover": turnover}
        status = "supported" if all(c["verdict"] == "supports" for c in cells.values()) else \
            "rejected" if any(c["verdict"] == "contradicts" for c in cells.values()) else "testing"
        results[rid] = {"parent": parent_id, "status": status, "cells": cells}
        print(rid, "->", status)
        for w, c in cells.items():
            print(f"  {w} f45@7 {c['net_active_f45_7bps']:+6.1%}  control(close) {c['net_active_control_close']:+6.1%}  "
                  f"parent {c['net_active_parent_3_45_close']:+6.1%}  gain {c['gain_vs_control']:+6.1%}  boot {c['bootstrap_p']:.2f}  "
                  f"upper {c['net_active_upper_bound_sig45_fill45']:+6.1%}  by cost {c['net_active_by_cost']}  turn {c['turnover']:.0f}  "
                  f"n {c['decisions']} {c['start']} -> {c['verdict']}: {'; '.join(c['why'])}", flush=True)

    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"fills_{stamp}.json"
    ledger_ids = lookup(conn)
    for rid, res in results.items():
        hid = ledger_ids[title_of(rid)]
        for w, c in res["cells"].items():
            summary = (f"round14_fills {rid} {w} from {c['start']}: {c['decisions']} decisions; 3:30 signal filled at 3:45 (7 bps) net active "
                       f"{c['net_active_f45_7bps']:.2%}/yr vs the same signal filled at the close (5 bps) {c['net_active_control_close']:.2%}; "
                       f"gain {c['gain_vs_control']:.2%}/yr, bootstrap P(gain>0) {c['bootstrap_p']:.2f}; parent (3:45 signal, close fill) "
                       f"{c['net_active_parent_3_45_close']:.2%}; by fill cost {c['net_active_by_cost']}; upper bound (3:45 signal, 3:45 fill, 7 bps) "
                       f"{c['net_active_upper_bound_sig45_fill45']:.2%}. {c['verdict']}: {'; '.join(c['why'])}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
        set_status(conn, hid, res["status"])
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "data_check": report, "bar": {"gain": BAR_DIFF, "bootstrap": BOOT_MIN},
                                "costs": {"close": CLOSE_BPS, "fill": FILL_BPS}, "results": results}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
