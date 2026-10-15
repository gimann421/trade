"""Score hypotheses 121-124 of research/r12-vix-residual-volume-fomc-2026-10-15.md (the pre-FOMC test is round12_fomc.py).

    PYTHONPATH=. python research/round12_ideas.py --register
    PYTHONPATH=. python research/round12_ideas.py --universe all
    PYTHONPATH=. python research/round12_ideas.py --universe holdout
    PYTHONPATH=. python research/round12_ideas.py --finalize
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import DATA_DIR, load_bars
from core.industry import load_sic
from core.ledger import add_evidence, add_hypothesis, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import (BAR, COSTS, WINDOWS, break_even_bps, cleaned, dirty_index, placebo,
                                           weeks_to_confidence)
from research.round10_neighbours import MIN_AGREE, MIN_DECISIONS, load_inputs
from research.round11_ideas import judge

MEMO = "research/r12-vix-residual-volume-fomc-2026-10-15.md"
HYPOTHESES_BEFORE = 120
OUT_DIR = ROOT / "backtests" / "short_horizon_v5"
VIX_PATH = DATA_DIR / "long" / "fred" / "VIXCLS.csv"


def title_of(rule: dict) -> str:
    return f"Short-horizon v5: {rule['id']}"


def describe(rule: dict) -> str:
    return (f"Round 12 variant {rule['id']} of the 3-session band reversal rule (see {MEMO}): beats the equal-weight members "
            f">= 2.0%/yr net with IR >= 0.3, placebo >= 0.95, positive at 10 bps and with the 15:30 price, in both IS "
            f"2017-2022 and OOS 2023+, on all 718 names and on the 418 unseen names.")


def register(conn, rules) -> dict:
    ids = lookup(conn)
    for rule in rules:
        if title_of(rule) not in ids:
            ids[title_of(rule)] = add_hypothesis(conn, title_of(rule), describe(rule),
                                                 rationale="Round 12: VIX state, residual reversal and volume filter on the band reversal rule.",
                                                 research_memo=MEMO, strategy="short_horizon_v5.py")
    return {r["id"]: ids[title_of(r)] for r in rules}


def run(universe: str):
    sh, fs = load_module("short_horizon_v5"), load_module("factor_scan_v1")
    conn = connect()
    register(conn, sh.RULES)
    membership, index, close, open_, snaps, report = load_inputs(None, universe)
    print("data check:", json.dumps(report))
    if min(report[f]["share_within"] for f in ("p1530", "p1545")) < MIN_AGREE:
        print("snapshot data fails the pre-registered agreement check; stopping")
        return
    stocks = list(close.columns)
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    cols = list(full.columns)
    dirty = dirty_index(index)
    fs.FIRST_DECISION = sh.FIRST_DECISION
    members_fn = lambda dates: members_on(membership, dates)
    monthly = index[month_ends(index)]
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    _, bench_targets, bench_detail = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, cols), monthly, membership, None)
    bench = {n: cleaned(simulate(close_ff, bench_targets, b), dirty) for n, b in COSTS.items()}
    first_hold = index[index.get_loc(bench_detail[0]["date"]) + 1]

    vix = pd.read_csv(VIX_PATH, index_col=0, parse_dates=True)["VIXCLS"].astype(float)
    shares = {m: sh.vix_share(vix, index, m) for m in ("gate", "scale")}
    sic = load_sic()
    ratio = sh.volume_ratio(snaps["vol1545"].reindex(columns=stocks)).reindex(columns=cols)

    def scores_for(signal, price):
        snap = snaps[price].reindex(columns=stocks)
        s = sh.residual_matrix(close, snap) if signal == "rev5r" else sh.rev5_matrix(close, snap)
        return s.reindex(columns=cols)

    rules = [sh.PARENT_RULE] + sh.RULES
    results, stamp = {}, pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"short_horizon_v5_{universe}_{stamp}.json"
    for rule in rules:
        decisions = sh.decision_dates(index)
        runs, details = {}, {}
        for variant, price, bps in (("primary", "p1545", 5.0), ("stress", "p1545", 10.0), ("noisy", "p1530", 5.0)):
            targets, detail = sh.generate_targets(rule, full, scores_for(rule["signal"], price), decisions, members_fn,
                                                  share=shares.get(rule["vix"]), groups=sic if rule["signal"] == "rev5r" else None,
                                                  ratio=ratio if rule["signal"] == "rev5v" else None)
            runs[variant] = cleaned(simulate(close_ff, targets, bps), dirty)
            details[variant] = detail
        windows = holding_windows(details["primary"], index)
        cells = {}
        for label, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
            net = lambda name, b: window_stats(runs[name], bench[b], first_hold, start, end)[2]["net_active"]
            stress_active, noisy_active = net("stress", "stress"), net("noisy", "primary")
            _, pct = placebo(details["primary"], close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            extra = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
            gross = stats["net_active"] + extra * COSTS["primary"] / 1e4
            verdict, why = judge(label, n, MIN_DECISIONS[3], stats, pct, stress_active, noisy_active)
            cells[label] = {"verdict": verdict, "why": why, "decisions": n, "net_active": stats["net_active"],
                            "information_ratio": stats["information_ratio"], "placebo": pct, "gross_active": gross,
                            "annual_turnover": stats["annual_turnover"], "break_even_bps": break_even_bps(gross, extra),
                            "stress_net_active": stress_active, "noisy_net_active": noisy_active,
                            "beta": stats["beta_to_benchmark"], "start": stats["start"], "end": stats["end"]}
        whole = window_stats(runs["primary"], bench["primary"], first_hold, "2016-01-01", None)[2]
        active_share = float(np.mean([d["share"] for d in details["primary"]]))
        results[rule["id"]] = {"rule": rule, "cells": cells, "information_ratio_all": whole["information_ratio"],
                               "net_active_all": whole["net_active"], "mean_active_share": active_share,
                               "weeks_to_confidence": weeks_to_confidence(whole["information_ratio"])}
        print(f"{rule['id']:26s} share {active_share:.2f} " + "  ".join(
            f"{w} act {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} gross {c['gross_active']:+6.1%} "
            f"turn {c['annual_turnover']:4.0f} 10bp {c['stress_net_active']:+6.1%} 1530 {c['noisy_net_active']:+6.1%}"
            for w, c in cells.items()) + "  -> " + "/".join(c["verdict"] for c in cells.values()), flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger_ids = lookup(conn)
    for rid, res in results.items():
        if res["rule"]["role"] == "parent":
            continue
        hid = ledger_ids[title_of(res["rule"])]
        for w, c in res["cells"].items():
            be = f"{c['break_even_bps']:.1f}" if c["break_even_bps"] is not None else "n/a"
            summary = (f"short_horizon_v5 {rid} [{universe} universe, {report['tickers']} tickers] {w} {c['start']}..{c['end']}, 5 bps, 15:45 snapshot fill at the close: "
                       f"{c['decisions']} decisions, net active {c['net_active']:.2%}/yr (gross {c['gross_active']:.2%}), IR {c['information_ratio']:.2f}, "
                       f"placebo {c['placebo']:.3f}, turnover {c['annual_turnover']:.0f}x/yr, break-even {be} bps; 10 bps {c['stress_net_active']:.2%}, "
                       f"15:30 signal {c['noisy_net_active']:.2%}. {c['verdict']}: {'; '.join(c['why'])}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "universe": universe, "data_check": report,
                                "bar": BAR, "costs": COSTS, "results": results}, indent=1, default=str) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def latest(universe):
    files = sorted(OUT_DIR.glob(f"short_horizon_v5_{universe}_*.json"))
    return json.loads(files[-1].read_text()) if files else None


def finalize():
    sh = load_module("short_horizon_v5")
    a, h = latest("all"), latest("holdout")
    conn = connect()
    ledger_ids = lookup(conn)
    passing = []
    for rule in sh.RULES:
        rid = rule["id"]
        flags = {n: all(c["verdict"] == "supports" for c in d["results"][rid]["cells"].values()) for n, d in (("all", a), ("holdout", h))}
        gross_ok = any(c["gross_active"] >= 0.04 for c in a["results"][rid]["cells"].values())
        supported = flags["all"] and flags["holdout"] and gross_ok
        rejected = any(c["verdict"] == "contradicts" for d in (a, h) for c in d["results"][rid]["cells"].values())
        status = "supported" if supported else "rejected" if rejected else "testing"
        if supported:
            passing.append(rid)
        hid = ledger_ids[title_of(rule)]
        set_strategy(conn, hid, "short_horizon_v5.py")
        set_status(conn, hid, status)
        print(f"{rid:26s} all={flags['all']} holdout={flags['holdout']} -> {status}")
    note = (f"Round 12 reversal variants (hypotheses 121-124): {len(passing)} of {len(sh.RULES)} pass the raised bar: "
            f"{', '.join(passing) or 'none'}.")
    conn.close()
    print(note)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--universe", choices=["all", "holdout"])
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.register:
        conn = connect()
        ids = register(conn, load_module("short_horizon_v5").RULES)
        print(f"{len(ids)} rules registered, ids {min(ids.values())}-{max(ids.values())}")
    elif args.finalize:
        finalize()
    elif args.universe:
        run(args.universe)


if __name__ == "__main__":
    sys.exit(main())
