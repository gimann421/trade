"""Round 15: the 3-session band reversal rule ranked within one half of the names, split by three filter variables.

    PYTHONPATH=. python research/round15_filters.py --register
    PYTHONPATH=. python research/round15_filters.py [--dry]
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
from core.intraday import sample_tickers
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on,
                           month_end_members)
from research.round15_common import MEMO, RULES, register, title_of
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import WINDOWS, break_even_bps, cleaned, dirty_index, placebo
from research.round9_executable import load_inputs

OUT_DIR = ROOT / "backtests" / "round15_filters"
FIRST_DECISION = "2017-01-03"
HOLD, RULE_ID = 3, "rev5_h3_band40_s"
MIN_DECISIONS = {"IS": 160, "OOS": 100}
BAR = {"net_active": 0.02, "information_ratio": 0.3, "placebo": 0.95}
FILTERS = {"F1": "far from the 52-week high", "F2": "medium-term losers", "F3": "low volatility"}


def filter_values(name, price, close):
    if name == "F1":
        return price / close.shift(1).rolling(252, min_periods=200).max()
    if name == "F2":
        return close.shift(21) / close.shift(252) - 1
    if name == "F3":
        return close.pct_change(fill_method=None).shift(1).rolling(60, min_periods=50).std()
    raise ValueError(name)


def halves(signal, values, decisions):
    """Signal restricted to the below-median half and to the at-or-above-median half of the filter, per decision day."""
    test, mirror = pd.DataFrame(np.nan, signal.index, signal.columns), pd.DataFrame(np.nan, signal.index, signal.columns)
    for d in decisions:
        s, v = signal.loc[d], values.loc[d]
        ok = s.notna() & v.notna()
        if ok.sum() < 20:
            continue
        med = v[ok].median()
        test.loc[d, ok & (v < med)] = s[ok & (v < med)]
        mirror.loc[d, ok & (v >= med)] = s[ok & (v >= med)]
    return test, mirror


def evaluate(label, close, snaps, sh, fs, membership, variants, decisions, bench_targets, first_hold, dirty, rule):
    """Returns {unit: {window: cell}} for the parent and both halves of every filter."""
    index = close.index
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    members_fn = lambda dates: members_on(membership, dates)
    bench = {name: cleaned(simulate(close_ff, bench_targets, bps), dirty) for name, bps in {"5": 5.0, "10": 10.0}.items()}
    results = {}
    units = {"parent": None}
    for f in FILTERS:
        units[f"{f}_test"] = (f, True)
        units[f"{f}_mirror"] = (f, False)
    cache = {}
    for variant, price_name, bps in variants:
        price = close if price_name == "close" else snaps[price_name].reindex(index=index, columns=close.columns)
        rev = -(price / close.shift(5) - 1)
        rev[sh.CASH] = np.nan
        for f in FILTERS:
            vals = filter_values(f, price, close)
            vals[sh.CASH] = np.nan
            cache[(variant, f)] = halves(rev, vals, decisions)
        cache[(variant, "parent")] = rev
    for unit, spec in units.items():
        runs, details = {}, {}
        for variant, price_name, bps in variants:
            scores = cache[(variant, "parent")] if spec is None else cache[(variant, spec[0])][0 if spec[1] else 1]
            targets, detail = sh.generate_targets(rule, full, scores, None, decisions, members_fn)
            runs[variant] = cleaned(simulate(close_ff, targets, bps), dirty)
            details[variant] = detail
        windows = holding_windows(details["primary"], index)
        cells = {}
        for w, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(runs["primary"], bench["5"], first_hold, start, end)
            stress = window_stats(runs["stress"], bench["10"], first_hold, start, end)[2]["net_active"]
            noisy = window_stats(runs["noisy"], bench["5"], first_hold, start, end)[2]["net_active"] if "noisy" in runs else None
            gross_per_period, pct = placebo(details["primary"], close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            extra_turn = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
            gross = stats["net_active"] + extra_turn * 5.0 / 1e4
            cells[w] = {"decisions": n, "net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                        "placebo": pct, "gross_active": gross, "turnover": stats["annual_turnover"],
                        "break_even_bps": break_even_bps(gross, extra_turn), "stress_net_active": stress, "noisy_net_active": noisy,
                        "ranked_median": float(np.median([len(d["ranked"]) for d in details["primary"] if d["ranked"]] or [0])),
                        "start": stats["start"], "end": stats["end"]}
        results[unit] = cells
        print(label, f"{unit:10s}", "  ".join(
            f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%}"
            + (f" 1530 {c['noisy_net_active']:+6.1%}" if c["noisy_net_active"] is not None else "") + f" turn {c['turnover']:4.0f} n {c['decisions']}"
            for w, c in cells.items()), flush=True)
    return results


def judge_cell(cell, parent, need, needs_noisy):
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
        fails.append(f"10 bps net active {cell['stress_net_active']:.2%} not above 0")
    if needs_noisy and not cell["noisy_net_active"] > 0:
        fails.append(f"15:30-signal net active {cell['noisy_net_active']:.2%} not above 0")
    if not cell["net_active"] > parent["net_active"]:
        fails.append(f"net active {cell['net_active']:.2%} does not beat the parent's {parent['net_active']:.2%}")
    return ("contradicts", fails) if fails else ("supports", ["passes the bar and beats the parent"])


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
    fs, sh = load_module("factor_scan_v1"), load_module("short_horizon_v3")
    sh.FIRST_DECISION = FIRST_DECISION
    fs.FIRST_DECISION = FIRST_DECISION
    rule = next(r for r in sh.RULES if r["id"] == RULE_ID)
    membership = load_membership()
    index = load_bars("VTI").index
    wanted = sorted(month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END))
    close_all = load_member_panel(wanted, "close").reindex(index)
    sample = set(sample_tickers())
    dirty = dirty_index(index)
    decisions = sh.decision_dates(index, HOLD)
    monthly = index[month_ends(index)]
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}

    def bench_for(close):
        full = close.copy()
        full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
        _, targets, detail = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, full.columns), monthly, membership, None)
        return targets, index[index.get_loc(detail[0]["date"]) + 1]

    out = {}
    print(f"decisions {len(decisions)}, names {close_all.shape[1]}", flush=True)
    bt, fh = bench_for(close_all)
    out["screen_all"] = evaluate("screen_all", close_all, None, sh, fs, membership,
                                 [("primary", "close", 5.0), ("stress", "close", 10.0)], decisions, bt, fh, dirty, rule)
    unseen = close_all[[c for c in close_all.columns if c not in sample]]
    bt, fh = bench_for(unseen)
    out["screen_unseen"] = evaluate("screen_unseen", unseen, None, sh, fs, membership,
                                    [("primary", "close", 5.0), ("stress", "close", 10.0)], decisions, bt, fh, dirty, rule)
    membership_, index_, close_s, open_s, snaps, report = load_inputs(sh)
    print("snapshot data check:", json.dumps(report), flush=True)
    bt, fh = bench_for(close_s)
    out["snapshot"] = evaluate("snapshot", close_s, snaps, sh, fs, membership, [("primary", "p1545", 5.0), ("stress", "p1545", 10.0),
                                                                              ("noisy", "p1530", 5.0)], decisions, bt, fh, dirty, rule)

    verdicts = {}
    for rid, f, _ in RULES:
        cells = {}
        for ev, needs_noisy in (("screen_all", False), ("screen_unseen", False), ("snapshot", True)):
            for w in WINDOWS:
                v, why = judge_cell(out[ev][f"{f}_test"][w], out[ev]["parent"][w], MIN_DECISIONS[w], needs_noisy)
                cells[f"{ev}/{w}"] = {"verdict": v, "why": why}
        vs = {c["verdict"] for c in cells.values()}
        screens = {c["verdict"] for k, c in cells.items() if k.startswith("screen")}
        status = "supported" if vs == {"supports"} else "rejected" if "contradicts" in vs and screens != {"supports"} else \
            "testing" if screens == {"supports"} else "rejected"
        verdicts[rid] = {"filter": f, "status": status, "cells": cells}
        print(rid, "->", status)
        for k, c in cells.items():
            print("   ", k, c["verdict"], "; ".join(c["why"]))
    mirror_flags = {}
    for rid, f, _ in RULES:
        flags = {}
        for ev, needs_noisy in (("screen_all", False), ("screen_unseen", False), ("snapshot", True)):
            flags[ev] = {w: judge_cell(out[ev][f"{f}_mirror"][w], out[ev]["parent"][w], MIN_DECISIONS[w], needs_noisy)[0] for w in WINDOWS}
        mirror_flags[rid] = flags
    print("mirror halves (report only):", json.dumps(mirror_flags))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"filters_{stamp}.json"
    ledger_ids = lookup(conn)
    for rid, res in verdicts.items():
        hid = ledger_ids[title_of(rid)]
        f = res["filter"]
        for ev in ("screen_all", "screen_unseen", "snapshot"):
            for w in WINDOWS:
                c, p, m = out[ev][f"{f}_test"][w], out[ev]["parent"][w], out[ev][f"{f}_mirror"][w]
                cell = res["cells"][f"{ev}/{w}"]
                summary = (f"round15_filters {rid} [{FILTERS[f]}] {ev} {w} {c['start']}..{c['end']}, 5 bps: {c['decisions']} decisions, net active "
                           f"{c['net_active']:.2%}/yr, IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}, 10 bps {c['stress_net_active']:.2%}"
                           + (f", 15:30 signal {c['noisy_net_active']:.2%}" if c["noisy_net_active"] is not None else "")
                           + f", turnover {c['turnover']:.0f}x; parent {p['net_active']:.2%} (IR {p['information_ratio']:.2f}); opposite half {m['net_active']:.2%} "
                           f"(IR {m['information_ratio']:.2f}). {cell['verdict']}: {'; '.join(cell['why'])}")
                add_evidence(conn, hid, "backtest", summary, cell["verdict"], ref=str(path.relative_to(ROOT)))
        set_status(conn, hid, res["status"])
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "bar": BAR, "first_decision": FIRST_DECISION,
                                "results": out, "verdicts": verdicts, "mirror": mirror_flags}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
