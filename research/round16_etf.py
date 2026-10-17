"""Test 2 of round 16: the 3-session band reversal rule on volatility-scaled 5-day returns across liquid ETFs.

    PYTHONPATH=. python research/round16_etf.py --register
    PYTHONPATH=. python research/round16_etf.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.ledger import add_evidence, connect, set_status
from core.portfolio import month_ends, simulate
from research.round16_common import ETFS, MEMO, register, title_of
from research.round16_data import load_etfs
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import WINDOWS, break_even_bps, cleaned, dirty_index, placebo

OUT_DIR = ROOT / "backtests" / "round16_etf"
FIRST_DECISION = "2017-01-03"
MIN_DECISIONS = {"IS": 160, "OOS": 100}
BAR = {"net_active": 0.02, "information_ratio": 0.3, "placebo": 0.95}
COSTS = {"primary": 2.0, "stress": 5.0, "wide": 10.0}
HISTORY, DOLLAR_VOLUME = 260, 20e6
NON_EQUITY = set("TLT IEF SHY IEI TLH LQD HYG JNK AGG BND TIP MUB EMB BNDX VCSH VCIT VCLT BKLN MBB GOVT SPSB "
                 "GLD SLV IAU USO UNG DBC DBA DBB UUP FXE FXY FXA FXB FXC PPLT PALL CPER".split())


def eligibility(close, volume):
    history = close.notna().cumsum() >= HISTORY
    dollar = (close * volume).rolling(60, min_periods=50).median() >= DOLLAR_VOLUME
    return history & dollar & close.notna()


def signals(close):
    ret = close.pct_change(fill_method=None)
    raw = -(close / close.shift(5) - 1)
    return {"scaled5": raw / (ret.rolling(60, min_periods=50).std() * np.sqrt(5)), "raw5": raw,
            "scaled1": -ret / ret.rolling(60, min_periods=50).std(),
            "scaled10": -(close / close.shift(10) - 1) / (ret.rolling(60, min_periods=50).std() * np.sqrt(10))}


def bench_targets(index, columns, elig, decisions):
    out = pd.DataFrame(np.nan, index, columns)
    for d in decisions:
        names = list(elig.columns[elig.loc[d].to_numpy()])
        out.loc[d] = 0.0
        if names:
            out.loc[d, names] = 1.0 / len(names)
    return out


def run_variant(label, score, hold, elig, close, close_ff, sh, rule, dirty, equities_only=False):
    index = close.index
    use = elig.copy()
    if equities_only:
        use.loc[:, [c for c in use.columns if c in NON_EQUITY]] = False
    decisions = sh.decision_dates(index, hold)
    monthly = [d for d in index[month_ends(index)] if d >= pd.Timestamp(FIRST_DECISION)]
    members_fn = lambda dates: [frozenset(use.columns[use.loc[d].to_numpy()]) for d in dates]
    targets, detail = sh.generate_targets(rule, close, score, None, decisions, members_fn)
    bt = bench_targets(index, close.columns, use, monthly)
    first_hold = index[index.get_loc(monthly[0]) + 1]
    windows = holding_windows(detail, index)
    cells = {}
    runs = {name: cleaned(simulate(close_ff, targets, bps), dirty) for name, bps in COSTS.items()}
    bench = {name: cleaned(simulate(close_ff, bt, bps), dirty) for name, bps in COSTS.items()}
    for w, (start, end) in WINDOWS.items():
        _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
        stress = window_stats(runs["stress"], bench["stress"], first_hold, start, end)[2]["net_active"]
        wide = window_stats(runs["wide"], bench["wide"], first_hold, start, end)[2]["net_active"]
        gross_per_period, pct = placebo(detail, close_ff, index, start, end, dirty)
        n = sum(in_window(first, start, end) for _, first, _ in windows)
        extra_turn = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
        gross = stats["net_active"] + extra_turn * COSTS["primary"] / 1e4
        cells[w] = {"decisions": n, "net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                    "placebo": pct, "gross_active": gross, "turnover": stats["annual_turnover"],
                    "break_even_bps": break_even_bps(gross, extra_turn), "stress_net_active": stress,
                    "wide_net_active": wide, "start": stats["start"], "end": stats["end"],
                    "ranked_median": float(np.median([len(d["ranked"]) for d in detail if d["ranked"]] or [0])),
                    "cagr": stats["strategy"]["cagr"], "benchmark_cagr": stats["benchmark"]["cagr"]}
    print(f"{label:28s}", "  ".join(
        f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 5bp {c['stress_net_active']:+6.1%} "
        f"10bp {c['wide_net_active']:+6.1%} turn {c['turnover']:4.0f} n {c['decisions']} univ {c['ranked_median']:.0f}"
        for w, c in cells.items()), flush=True)
    return cells


def judge_cell(cell, need):
    if cell["decisions"] < need:
        return "inconclusive", [f"only {cell['decisions']} decisions (need {need})"]
    fails = []
    if cell["net_active"] < BAR["net_active"]:
        fails.append(f"net active {cell['net_active']:.2%} < 2.0%")
    if cell["information_ratio"] < BAR["information_ratio"]:
        fails.append(f"IR {cell['information_ratio']:.2f} < 0.3")
    if cell["placebo"] < BAR["placebo"]:
        fails.append(f"placebo {cell['placebo']:.3f} < 0.95")
    if cell["stress_net_active"] <= 0:
        fails.append(f"5 bps net active {cell['stress_net_active']:.2%} not above 0")
    return ("contradicts", fails) if fails else ("supports", ["passes the bar"])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    conn = connect()
    ids = register(conn)
    if args.register:
        print(f"registered {ids}")
        return
    sh = load_module("short_horizon_v3")
    sh.FIRST_DECISION = FIRST_DECISION
    rule = next(r for r in sh.RULES if r["id"] == "rev5_h3_band40_s")
    close, volume = load_etfs()
    index = close.index
    close_ff = close.ffill()
    dirty = dirty_index(index)
    elig = eligibility(close, volume)
    big = int(((close.pct_change(fill_method=None).abs() > 0.3) & elig).sum().sum())
    report = {"etfs_downloaded": close.shape[1], "of": len(ETFS), "first": str(index[0].date()), "last": str(index[-1].date()),
              "eligible_median": float(elig.loc[FIRST_DECISION:].sum(axis=1).median()), "moves_over_30pct_when_eligible": big}
    print("data check:", json.dumps(report), flush=True)
    sigs = signals(close)
    out = {"primary": run_variant("scaled5 h3 (the test)", sigs["scaled5"], 3, elig, close, close_ff, sh, rule, dirty)}
    out["raw5"] = run_variant("report: raw5 h3", sigs["raw5"], 3, elig, close, close_ff, sh, rule, dirty)
    out["scaled5_equities"] = run_variant("report: scaled5 equities only", sigs["scaled5"], 3, elig, close, close_ff, sh, rule, dirty, True)
    out["scaled1_h1"] = run_variant("report: scaled1 h1", sigs["scaled1"], 1, elig, close, close_ff, sh, rule, dirty)
    out["scaled10_h3"] = run_variant("report: scaled10 h3", sigs["scaled10"], 3, elig, close, close_ff, sh, rule, dirty)
    cells = {}
    for w in WINDOWS:
        v, why = judge_cell(out["primary"][w], MIN_DECISIONS[w])
        cells[w] = {"verdict": v, "why": why}
    vs = {c["verdict"] for c in cells.values()}
    status = "supported" if vs == {"supports"} else "rejected" if "contradicts" in vs else "testing"
    print("verdict:", status, json.dumps(cells))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"etf_{stamp}.json"
    hid = lookup(conn)[title_of("rev5s_h3_band40_etf")]
    for w in WINDOWS:
        c = out["primary"][w]
        summary = (f"round16_etf rev5s_h3_band40_etf {w} {c['start']}..{c['end']}, 2 bps: {c['decisions']} decisions, net active {c['net_active']:.2%}/yr, "
                   f"IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}, 5 bps {c['stress_net_active']:.2%}, 10 bps {c['wide_net_active']:.2%}, "
                   f"turnover {c['turnover']:.0f}x/yr, median eligible ETFs {c['ranked_median']:.0f}; raw 5-day signal {out['raw5'][w]['net_active']:.2%}, "
                   f"equities only {out['scaled5_equities'][w]['net_active']:.2%}. {cells[w]['verdict']}: {'; '.join(cells[w]['why'])}. "
                   f"Survivorship caveat: list of ETFs alive today.")
        add_evidence(conn, hid, "backtest", summary, cells[w]["verdict"], ref=str(path.relative_to(ROOT)))
    set_status(conn, hid, status)
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "bar": BAR, "costs": COSTS, "data": report,
                                "results": out, "verdict": status, "cells": cells}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
