"""Score the 9 snapshot-fill rules of research/r9-executable-short-horizon-2026-10-14.md (hypotheses 94-102).

    PYTHONPATH=. python research/round9_executable.py --register   # add the 9 rules to the ledger as proposed
    PYTHONPATH=. python research/round9_executable.py --check      # data check only, no returns
    PYTHONPATH=. python research/round9_executable.py              # score them
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.intraday import load_snapshots, sample_tickers
from core.ledger import add_evidence, add_hypothesis, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, STOCK_DIR, load_member_panel, load_membership,
                           members_on, month_end_members)
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import (BAR, COSTS, WINDOWS, break_even_bps, cleaned, dirty_index, placebo,
                                           weeks_to_confidence)

MEMO = "research/r9-executable-short-horizon-2026-10-14.md"
MIN_DECISIONS = {2: {"IS": 250, "OOS": 150}, 5: {"IS": 48, "OOS": 36}}
HYPOTHESES_BEFORE = 93
OUT_DIR = ROOT / "backtests" / "short_horizon_v2"
MAX_GAP = 0.05
MIN_AGREE = 0.999


def describe(rule: dict) -> str:
    kind = {"plain": "the top decile", "band": "the top decile with a keep-while-top-30% band",
            "lv": "the top decile of names with at most normal volume"}[rule["kind"]]
    return (f"Every {rule['hold']} sessions, reading the 15:45 price and filling at the close, holding {kind} of "
            f"point-in-time S&P 500 members by {rule['signal']}, equal weight, beats the equal-weight members by "
            f">= 2.0%/yr net with information ratio >= 0.3, placebo >= 0.95, and stays positive at 10 bps and with a "
            f"15:30 signal, in both IS 2017-2022 and OOS 2023+.")


def register(conn, rules) -> dict:
    ids = lookup(conn)
    for rule in rules:
        title = f"Short-horizon v2: {rule['id']}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, describe(rule),
                                        rationale="Round-9 snapshot-fill short-horizon rules; see the memo.",
                                        research_memo=MEMO, strategy="short_horizon_v2.py")
    return {r["id"]: ids[f"Short-horizon v2: {r['id']}"] for r in rules}


def judge(label, decisions, minimum, stats, pct, stress_active, noisy_active):
    """Returns (verdict, reasons, execution_sensitive)."""
    if decisions < minimum[label]:
        return "inconclusive", [f"only {decisions} decisions (need {minimum[label]})"], False
    bar_fails = []
    if stats["net_active"] < BAR["net_active"]:
        bar_fails.append(f"net active {stats['net_active']:.2%}/yr < 2.0%")
    if stats["information_ratio"] < BAR["information_ratio"]:
        bar_fails.append(f"information ratio {stats['information_ratio']:.2f} < 0.3")
    if pct < BAR["placebo"]:
        bar_fails.append(f"placebo {pct:.3f} < 0.95")
    extra = []
    if stress_active <= 0:
        extra.append(f"10 bps net active {stress_active:.2%} not above 0")
    if noisy_active <= 0:
        extra.append(f"15:30-signal net active {noisy_active:.2%} not above 0")
    if bar_fails:
        return "contradicts", bar_fails + extra, False
    if extra:
        return "contradicts", extra, True
    return "supports", ["passes the bar, the 10 bps stress and the 15:30-signal check"], False


def load_inputs(sh):
    membership = load_membership()
    sample = set(sample_tickers())
    wanted = sorted(t for t in month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END) if t in sample)
    index = load_bars("VTI").index
    close = load_member_panel(wanted, "close").reindex(index)
    open_ = load_member_panel(wanted, "open").reindex(index)
    snaps = {f: load_snapshots(wanted, f).reindex(index) for f in ("p1530", "p1545", "vol1545")}
    stocks = [c for c in close.columns if c in snaps["p1545"].columns]
    close, open_ = close[stocks], open_[stocks]
    for f in ("p1530", "p1545", "vol1545"):
        snaps[f] = snaps[f].reindex(columns=stocks)
    report = {"tickers": len(stocks)}
    for f in ("p1530", "p1545"):
        gap = (snaps[f] / close - 1).abs()
        have = gap.notna().to_numpy().sum()
        bad = (gap > MAX_GAP).to_numpy().sum()
        report[f] = {"name_sessions": int(have), "gap_over_5pct": int(bad), "share_within": float(1 - bad / have)}
        snaps[f] = snaps[f].where(~(gap > MAX_GAP))
    return membership, index, close, open_, snaps, report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    fs, sh = load_module("factor_scan_v1"), load_module("short_horizon_v2")
    conn = connect()
    ids = register(conn, sh.RULES)
    if args.register:
        print(f"{len(ids)} rules registered, ids {min(ids.values())}-{max(ids.values())}")
        return

    membership, index, close, open_, snaps, report = load_inputs(sh)
    print("data check:", json.dumps(report))
    if args.check:
        return
    if min(report[f]["share_within"] for f in ("p1530", "p1545")) < MIN_AGREE:
        print("snapshot data fails the pre-registered agreement check; stopping")
        return
    stocks = list(close.columns)
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    dirty = dirty_index(index)
    fs.FIRST_DECISION = sh.FIRST_DECISION
    members_fn = lambda dates: members_on(membership, dates)

    monthly = index[month_ends(index)]
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    none_scores = pd.DataFrame(np.nan, index, full.columns)
    _, bench_targets, bench_detail = fs.generate_targets(probe, full, none_scores, monthly, membership, None)
    bench = {name: cleaned(simulate(close_ff, bench_targets, bps), dirty) for name, bps in COSTS.items()}
    bench["late"] = cleaned(simulate(close_ff, bench_targets.shift(1), COSTS["primary"]), dirty)
    first_hold = index[index.get_loc(bench_detail[0]["date"]) + 1]

    def scores_for(signal, price):
        s = sh.score_matrix(signal, open_, close, None if price == "close" else snaps[price])
        s[sh.CASH] = np.nan
        return s

    ratios = {days: sh.volume_ratio(snaps["vol1545"], days).assign(**{sh.CASH: np.nan}) for days in (1, 5)}
    results, stamp = {}, pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"short_horizon_v2_{stamp}.json"
    for rule in sh.RULES:
        decisions = sh.decision_dates(index, rule["hold"])
        ratio = ratios[sh.WINDOW[rule["signal"]]] if rule["kind"] == "lv" else None
        runs, details = {}, {}
        for variant, price, bps in (("primary", "p1545", 5.0), ("stress", "p1545", 10.0), ("noisy", "p1530", 5.0),
                                    ("closed", "close", 5.0)):
            targets, detail = sh.generate_targets(rule, full, scores_for(rule["signal"], price), ratio, decisions, members_fn)
            runs[variant] = cleaned(simulate(close_ff, targets, bps), dirty)
            details[variant] = detail
            if variant == "primary":
                runs["late"] = cleaned(simulate(close_ff, targets.shift(1), COSTS["primary"]), dirty)
        windows = holding_windows(details["primary"], index)
        cells = {}
        for label, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
            net = lambda name, b: window_stats(runs[name], bench[b], first_hold, start, end)[2]["net_active"]
            stress_active, noisy_active = net("stress", "stress"), net("noisy", "primary")
            late_active, closed_active = net("late", "late"), net("closed", "primary")
            gross_per_period, pct = placebo(details["primary"], close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            extra_turnover = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
            gross_active = stats["net_active"] + extra_turnover * COSTS["primary"] / 1e4
            verdict, why, sensitive = judge(label, n, MIN_DECISIONS[rule["hold"]], stats, pct, stress_active, noisy_active)
            cells[label] = {"verdict": verdict, "why": why, "execution_sensitive": sensitive, "decisions": n,
                            "net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                            "placebo": pct, "gross_active": gross_active, "annual_turnover": stats["annual_turnover"],
                            "break_even_bps": break_even_bps(gross_active, extra_turnover),
                            "stress_net_active": stress_active, "noisy_net_active": noisy_active,
                            "delayed_net_active": late_active, "close_timed_net_active": closed_active,
                            "beta": stats["beta_to_benchmark"], "start": stats["start"], "end": stats["end"]}
        whole = window_stats(runs["primary"], bench["primary"], first_hold, "2016-01-01", None)[2]
        status = "supported" if all(c["verdict"] == "supports" for c in cells.values()) else \
            "rejected" if any(c["verdict"] == "contradicts" for c in cells.values()) else "testing"
        results[rule["id"]] = {"rule": rule, "status": status, "cells": cells,
                               "information_ratio_all": whole["information_ratio"], "net_active_all": whole["net_active"],
                               "weeks_to_confidence": weeks_to_confidence(whole["information_ratio"])}
        print(f"{rule['id']:16s} " + "  ".join(
            f"{w} act {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} gross {c['gross_active']:+6.1%} "
            f"turn {c['annual_turnover']:4.0f} 10bp {c['stress_net_active']:+6.1%} 1530 {c['noisy_net_active']:+6.1%} "
            f"closed {c['close_timed_net_active']:+6.1%}" for w, c in cells.items()) + f"  -> {status}", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger_ids = lookup(conn)
    for rid, res in results.items():
        hid = ledger_ids[f"Short-horizon v2: {rid}"]
        for w, c in res["cells"].items():
            tag = " [execution-sensitive]" if c["execution_sensitive"] else ""
            be = f"{c['break_even_bps']:.1f}" if c["break_even_bps"] is not None else "n/a"
            summary = (f"short_horizon_v2 {rid} {w} {c['start']}..{c['end']}, 5 bps, 15:45 snapshot fill at the close: "
                       f"{c['decisions']} decisions, net active {c['net_active']:.2%}/yr (gross {c['gross_active']:.2%}), "
                       f"IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}, turnover {c['annual_turnover']:.0f}x/yr, "
                       f"break-even cost {be} bps; 10 bps {c['stress_net_active']:.2%}, 15:30 signal {c['noisy_net_active']:.2%}, "
                       f"close-timed {c['close_timed_net_active']:.2%}, delayed fill {c['delayed_net_active']:.2%}. "
                       f"{c['verdict']}{tag}: {'; '.join(c['why'])}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
        set_strategy(conn, hid, "short_horizon_v2.py")
        set_status(conn, hid, res["status"])
    passing = [r for r, v in results.items() if v["status"] == "supported"]
    note = (f"Round-9 snapshot-fill scan: {len(results)} rules, {len(passing)} supported ({', '.join(passing) or 'none'}). "
            f"Hypotheses tested so far: {HYPOTHESES_BEFORE + len(results)}.")
    for rid in passing:
        add_evidence(conn, ledger_ids[f"Short-horizon v2: {rid}"], "note", note, "supports")
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "data_check": report,
                                "dirty_sessions": [str(d.date()) for d in dirty], "bar": BAR, "costs": COSTS,
                                "note": note, "results": results}, indent=1, default=str) + "\n")
    print(note)
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
