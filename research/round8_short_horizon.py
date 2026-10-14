"""Score the 19 short-horizon rules of research/r8-short-horizon-2026-10-14.md (hypotheses 71-89).

    PYTHONPATH=. python research/round8_short_horizon.py --register   # add the 19 rules to the ledger as proposed
    PYTHONPATH=. python research/round8_short_horizon.py              # score them

Each rule is scored on its own against the bar fixed in the memo, plus the delayed-fill and 10 bps checks.
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, add_hypothesis, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, month_end_members)
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup

MEMO = "research/r8-short-horizon-2026-10-14.md"
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None)}
MIN_DECISIONS = {"IS": 48, "OOS": 36}
BAR = {"net_active": 0.02, "information_ratio": 0.3, "placebo": 0.95}
PLACEBO = {"n": 1000, "seed": 0}
COSTS = {"primary": 5.0, "stress": 10.0}
DIRTY = ("2020-03-09", "2020-03-20")
HYPOTHESES_BEFORE = 70
OUT_DIR = ROOT / "backtests" / "short_horizon_v1"
STATUS_VERDICT = {"rejected": "contradicts", "testing": "inconclusive", "supported": "supports"}


def describe(rule: dict) -> str:
    size = f"top {rule['fraction']:.0%}"
    return (f"Every {rule['hold']} sessions, holding the {size} of point-in-time S&P 500 members by {rule['signal']}, "
            f"equal weight, beats the equal-weight members by >= 2.0%/yr net with information ratio >= 0.3, "
            f"random-selection placebo >= 0.95, and still positive when filled a session late and at 10 bps, "
            f"in both IS 2017-2022 and OOS 2023+.")


def register(conn, rules) -> dict:
    ids = lookup(conn)
    for rule in rules:
        title = f"Short-horizon v1: {rule['id']}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, describe(rule),
                                        rationale="Round-8 short-horizon stock rules; see the memo.",
                                        research_memo=MEMO, strategy="short_horizon_v1.py")
    return {r["id"]: ids[f"Short-horizon v1: {r['id']}"] for r in rules}


def dirty_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index[(index >= pd.Timestamp(DIRTY[0])) & (index <= pd.Timestamp(DIRTY[1]))]


def cleaned(run: dict, dirty) -> dict:
    return {"returns": run["returns"].drop(dirty), "traded": run["traded"].drop(dirty)}


def placebo(detail, close_ff, index, start, end, dirty):
    """Percentile of the rule's mean gross active return per holding period among random same-size baskets,
    skipping holding periods that touch the excluded sessions."""
    rng = np.random.default_rng(PLACEBO["seed"])
    dirty_set = set(dirty)
    actual, draws = [], []
    for d, (date, first, last) in zip(detail, holding_windows(detail, index)):
        if not in_window(first, start, end) or not d["ranked"]:
            continue
        span = index[(index >= first) & (index <= last)]
        if any(day in dirty_set for day in span):
            continue
        growth = close_ff.loc[last] / close_ff.loc[date] - 1
        bench = growth[d["priced"]].mean()
        a = growth[d["picks"]].mean() - bench
        actual.append(a)
        ranked = growth[d["ranked"]].to_numpy()
        idx = np.argsort(rng.random((PLACEBO["n"], len(ranked))), axis=1)[:, :len(d["picks"])]
        draws.append(ranked[idx].mean(axis=1) - bench)
    mean = float(np.mean(actual))
    return mean, float((np.mean(np.array(draws), axis=0) < mean).mean())


def weeks_to_confidence(information_ratio: float):
    """Weeks of data until a t-statistic of 2 if the measured information ratio is the true one."""
    return float(52 * (2 / information_ratio) ** 2) if information_ratio > 0 else None


def break_even_bps(gross_active: float, extra_turnover: float):
    return float(gross_active / extra_turnover * 1e4) if extra_turnover > 0 else None


def judge(label, decisions, stats, pct, late_active, stress_active, minimum=MIN_DECISIONS):
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
    if late_active <= 0:
        extra.append(f"delayed-fill net active {late_active:.2%} not above 0")
    if stress_active <= 0:
        extra.append(f"10 bps net active {stress_active:.2%} not above 0")
    if bar_fails:
        return "contradicts", bar_fails + extra, False
    if extra:
        return "contradicts", extra, True
    return "supports", ["passes the bar and both execution checks"], False


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    fs, sh = load_module("factor_scan_v1"), load_module("short_horizon_v1")
    conn = connect()
    ids = register(conn, sh.RULES)
    if args.register:
        print(f"{len(ids)} rules registered, ids {min(ids.values())}-{max(ids.values())}")
        return

    membership = load_membership()
    wanted = sorted(month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END))
    index = load_bars("VTI").index
    close = load_member_panel(wanted, "close").reindex(index)
    open_ = load_member_panel(wanted, "open").reindex(index)
    close[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = close.ffill()
    stocks = [c for c in close.columns if c != sh.CASH]
    dirty = dirty_index(index)
    fs.FIRST_DECISION = sh.FIRST_DECISION

    # benchmark: equal-weight members, monthly
    monthly = index[month_ends(index)]
    probe = dict(sh.RULES[0], hold=1)
    none_scores = pd.DataFrame(np.nan, index, close.columns)
    _, bench_targets, bench_detail = fs.generate_targets(probe, close, none_scores, monthly, membership, None)
    bench = {name: cleaned(simulate(close_ff, bench_targets, bps), dirty) for name, bps in COSTS.items()}
    bench["late"] = cleaned(simulate(close_ff, bench_targets.shift(1), COSTS["primary"]), dirty)
    first_hold = index[index.get_loc(bench_detail[0]["date"]) + 1]

    scores = {sig: sh.score_matrix(sig, open_[stocks], close[stocks]) for sig in sh.SIGNALS}
    for frame in scores.values():
        frame[sh.CASH] = np.nan

    results, stamp = {}, pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"short_horizon_{stamp}.json"
    for rule in sh.RULES:
        decisions = sh.decision_dates(index, rule["hold"])
        targets, _, detail = fs.generate_targets(rule, close, scores[rule["signal"]], decisions, membership, None)
        runs = {"primary": cleaned(simulate(close_ff, targets, COSTS["primary"]), dirty),
                "stress": cleaned(simulate(close_ff, targets, COSTS["stress"]), dirty),
                "late": cleaned(simulate(close_ff, targets.shift(1), COSTS["primary"]), dirty)}
        windows = holding_windows(detail, index)
        cells = {}
        for label, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
            late_active = window_stats(runs["late"], bench["late"], first_hold, start, end)[2]["net_active"]
            stress_active = window_stats(runs["stress"], bench["stress"], first_hold, start, end)[2]["net_active"]
            gross_per_period, pct = placebo(detail, close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            extra_turnover = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
            gross_active = stats["net_active"] + extra_turnover * COSTS["primary"] / 1e4
            verdict, why, sensitive = judge(label, n, stats, pct, late_active, stress_active)
            cells[label] = {"verdict": verdict, "why": why, "execution_sensitive": sensitive, "decisions": n,
                            "net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                            "placebo": pct, "gross_active": gross_active, "annual_turnover": stats["annual_turnover"],
                            "break_even_bps": break_even_bps(gross_active, extra_turnover),
                            "delayed_net_active": late_active, "stress_net_active": stress_active,
                            "beta": stats["beta_to_benchmark"], "tracking_error": stats["tracking_error"],
                            "start": stats["start"], "end": stats["end"]}
        whole = window_stats(runs["primary"], bench["primary"], first_hold, "2016-01-01", None)[2]
        status = "supported" if all(c["verdict"] == "supports" for c in cells.values()) else \
            "rejected" if any(c["verdict"] == "contradicts" for c in cells.values()) else "testing"
        results[rule["id"]] = {"rule": rule, "status": status, "cells": cells, "information_ratio_all": whole["information_ratio"],
                               "net_active_all": whole["net_active"], "weeks_to_confidence": weeks_to_confidence(whole["information_ratio"])}
        print(f"{rule['id']:12s} " + "  ".join(
            f"{w} act {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} gross {c['gross_active']:+6.1%} "
            f"late {c['delayed_net_active']:+6.1%} 10bp {c['stress_net_active']:+6.1%}" for w, c in cells.items()) + f"  -> {status}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger_ids = lookup(conn)
    for rid, res in results.items():
        hid = ledger_ids[f"Short-horizon v1: {rid}"]
        for w, c in res["cells"].items():
            tag = " [execution-sensitive]" if c["execution_sensitive"] else ""
            be = f"{c['break_even_bps']:.1f}" if c["break_even_bps"] is not None else "n/a"
            summary = (f"short_horizon_v1 {rid} {w} {c['start']}..{c['end']}, 5 bps: {c['decisions']} decisions, net active "
                       f"{c['net_active']:.2%}/yr (gross {c['gross_active']:.2%}), IR {c['information_ratio']:.2f}, placebo "
                       f"{c['placebo']:.3f}, turnover {c['annual_turnover']:.0f}x/yr, break-even cost {be} bps; delayed fill "
                       f"{c['delayed_net_active']:.2%}, 10 bps {c['stress_net_active']:.2%}. {c['verdict']}{tag}: {'; '.join(c['why'])}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
        set_strategy(conn, hid, "short_horizon_v1.py")
        set_status(conn, hid, res["status"])
    passing = [r for r, v in results.items() if v["status"] == "supported"]
    note = (f"Round-8 short-horizon scan: {len(results)} rules, {len(passing)} supported ({', '.join(passing) or 'none'}). "
            f"Hypotheses tested so far: {HYPOTHESES_BEFORE + len(results)}.")
    for rid in passing:
        add_evidence(conn, ledger_ids[f"Short-horizon v1: {rid}"], "note", note, "supports")
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "dirty_sessions": [str(d.date()) for d in dirty],
                                "bar": BAR, "costs": COSTS, "note": note, "results": results}, indent=1, default=str) + "\n")
    print(note)
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
