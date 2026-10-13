"""Score the 37 rules of research/r6-factor-scan-2026-10-13.md (hypotheses 34-70).

    PYTHONPATH=. python research/round6_scan.py --register   # add the 37 rules to the ledger as proposed
    PYTHONPATH=. python research/round6_scan.py              # score them

Each rule is scored on its own against the bar fixed in the memo: in each window net active return
>= 2.0%/yr, information ratio >= 0.3, selection placebo >= 0.95, with at least 48 / 36 rebalances.
"""

import argparse
import importlib.util
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, add_hypothesis, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_closes, load_membership, members_on,
                           month_end_members)
from research.round5_verdicts import holding_windows, in_window, window_stats

MEMO = "research/r6-factor-scan-2026-10-13.md"
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None)}
MIN_REBALANCES = {"IS": 48, "OOS": 36}
COST_BPS = 5.0
BAR = {"net_active": 0.02, "information_ratio": 0.3, "placebo": 0.95}
PLACEBO = {"n": 1000, "seed": 0}
HYPOTHESES_BEFORE = 33
STATUS = {"IS": "in-sample", "OOS": "out-of-sample"}
OUT_DIR = ROOT / "backtests" / "factor_scan_v1"


def load_module(name: str):
    path = ROOT / "strategies" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def describe(rule: dict) -> str:
    if rule["family"] == "etf":
        return (f"Holding the top {rule['k']} of {', '.join(rule['tickers'])} by {rule['signal']}, equal weight, "
                f"monthly, beats the equal-weight universe by >= 2.0%/yr net with information ratio >= 0.3 and "
                f"random-selection placebo >= 0.95, in both IS and OOS.")
    size = f"{rule['fraction']:.0%} of ranked point-in-time S&P 500 members"
    cash = " (100% BIL when VTI is below its 200-day average)" if rule.get("trend") else ""
    return (f"Holding the top {size} by {rule['signal']}, equal weight, monthly{cash}, beats the equal-weight "
            f"members by >= 2.0%/yr net with information ratio >= 0.3 and random-selection placebo >= 0.95, "
            f"in both IS and OOS.")


def register(conn, rules) -> dict:
    ids = lookup(conn)
    for rule in rules:
        title = f"Scan v1: {rule['id']}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, describe(rule),
                                        rationale="Round-6 scan of rotation and factor rules; see the memo.",
                                        research_memo=MEMO, strategy="factor_scan_v1.py")
    return {r["id"]: ids[f"Scan v1: {r['id']}"] for r in rules}


def lookup(conn) -> dict:
    return {title: hid for hid, title in conn.execute("SELECT id, title FROM hypotheses")}


def load_inputs(fs, rm):
    membership = load_membership()
    wanted = sorted(month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END))
    index = load_bars("VTI").index
    stocks = load_member_closes(wanted).reindex(index)
    etf_names = sorted(set(fs.SECTORS) | set(fs.REGIONS) | {"VTI", fs.CASH} | set(rm.FACTOR_ETFS))
    etf = pd.DataFrame({s: load_bars(s)["close"] for s in etf_names}).reindex(index)
    if etf.isna().any().any():
        bad = etf.columns[etf.isna().any()].tolist()
        raise ValueError(f"ETF bars missing on trading days for {bad}; refresh with python -m core.data")
    clash = set(stocks.columns) & set(etf.columns)
    if clash:
        raise ValueError(f"ticker clash between stocks and ETFs: {sorted(clash)}")
    return membership, stocks, etf


def placebo(detail, close_ff, index, start, end):
    """Percentile of the rule's mean monthly gross active return among random same-size baskets."""
    rng = np.random.default_rng(PLACEBO["seed"])
    actual, draws = [], []
    for d, (date, first, last) in zip(detail, holding_windows(detail, index)):
        if not in_window(first, start, end):
            continue
        growth = close_ff.loc[last] / close_ff.loc[date] - 1
        bench = growth[d["priced"]].mean()
        a = growth[d["picks"]].mean() - bench
        actual.append(a)
        if d["off"] or not d["ranked"]:
            draws.append(np.full(PLACEBO["n"], a))
            continue
        ranked = growth[d["ranked"]].to_numpy()
        idx = np.argsort(rng.random((PLACEBO["n"], len(ranked))), axis=1)[:, :len(d["picks"])]
        draws.append(ranked[idx].mean(axis=1) - bench)
    mean = float(np.mean(actual))
    return mean, float((np.mean(np.array(draws), axis=0) < mean).mean())


def judge(label, rebalances, stats, pct):
    if rebalances < MIN_REBALANCES[label]:
        return "inconclusive", f"only {rebalances} rebalances (need {MIN_REBALANCES[label]})"
    fails = []
    if stats["net_active"] < BAR["net_active"]:
        fails.append(f"net active {stats['net_active']:.2%}/yr < 2.0%")
    if stats["information_ratio"] < BAR["information_ratio"]:
        fails.append(f"information ratio {stats['information_ratio']:.2f} < 0.3")
    if pct < BAR["placebo"]:
        fails.append(f"placebo {pct:.3f} < 0.95")
    return ("contradicts", "; ".join(fails)) if fails else ("supports", "passes the bar")


def clean_prices(close_ff):
    """Report-only: single-day moves below -50% or above +100% treated as data errors (spin-offs)."""
    r = close_ff.pct_change(fill_method=None)
    r = r.mask((r < -0.5) | (r > 1.0), 0.0)
    return (1 + r.fillna(0.0)).cumprod().where(close_ff.notna())


def score_rule(rule, fs, close_raw, scores, decisions, membership, trend, cache):
    index = close_raw.index
    close_ff = close_raw.ffill()
    targets, bench_targets, detail = fs.generate_targets(rule, close_raw, scores, decisions, membership, trend)
    key = tuple(rule["tickers"]) if rule["family"] == "etf" else "stock"
    if key not in cache:
        cache[key] = (simulate(close_ff, bench_targets, COST_BPS), simulate(close_ff, bench_targets.shift(1), COST_BPS))
    bench, bench_late = cache[key]
    run, run_late = simulate(close_ff, targets, COST_BPS), simulate(close_ff, targets.shift(1), COST_BPS)
    first_hold = index[index.get_loc(detail[0]["date"]) + 1]
    windows = holding_windows(detail, index)
    cells = {}
    for label, (start, end) in WINDOWS.items():
        s, b, stats = window_stats(run, bench, first_hold, start, end)
        _, _, late = window_stats(run_late, bench_late, first_hold, start, end)
        gross, pct = placebo(detail, close_ff, index, start, end)
        n = sum(in_window(first, start, end) for _, first, _ in windows)
        verdict, why = judge(label, n, stats, pct)
        cells[label] = {"verdict": verdict, "why": why, "rebalances": n, "net_active": stats["net_active"],
                        "information_ratio": stats["information_ratio"], "placebo": pct,
                        "gross_active_per_month": gross, "start": stats["start"], "end": stats["end"],
                        "beta": stats["beta_to_benchmark"], "turnover": stats["annual_turnover"],
                        "cagr": stats["strategy"]["cagr"], "benchmark_cagr": stats["benchmark"]["cagr"],
                        "sharpe": stats["strategy"]["sharpe"], "benchmark_sharpe": stats["benchmark"]["sharpe"],
                        "max_drawdown": stats["strategy"]["max_drawdown"],
                        "delayed_net_active": late["net_active"], "delayed_ir": late["information_ratio"],
                        "_curve": (1 + s).cumprod()}
    return cells, (targets, bench_targets, close_ff)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    conn = connect()
    ids = register(conn, fs.RULES)
    if args.register:
        print(f"{len(ids)} rules registered, ids {min(ids.values())}-{max(ids.values())}")
        return

    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    decisions = index[month_ends(index)]
    trend = fs.trend_series(etf["VTI"])
    cash = etf[fs.CASH]

    stock_close = stocks.copy()
    stock_close[fs.CASH] = cash
    stock_scores = {s: fs.score_matrix(s, stocks, etf["VTI"]) for s in fs.STOCK_SIGNALS if s != "resmom6_1"}
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    returns = stocks.pct_change(fill_method=None)
    res = pd.DataFrame(np.nan, index, stocks.columns)
    start_date = pd.Timestamp(fs.FIRST_DECISION)
    for date in [d for d in decisions if d >= start_date]:
        members = members_on(membership, [date])[0]
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        res.loc[date, priced] = rm.residual_scores(returns, factors, index.get_loc(date), priced,
                                                   **{k: v for k, v in fs.RESMOM6_1.items()}).reindex(priced).to_numpy()
    stock_scores["resmom6_1"] = res
    for scores in stock_scores.values():
        scores[fs.CASH] = np.nan

    cache, results, passers = {}, {}, {}
    for rule in fs.RULES:
        if rule["family"] == "etf":
            cols = list(rule["tickers"]) + [fs.CASH]
            close_raw = etf[cols]
            scores = fs.score_matrix(rule["signal"], etf[rule["tickers"]], etf["VTI"])
            scores[fs.CASH] = np.nan
        else:
            close_raw, scores = stock_close, stock_scores[rule["signal"]]
        cells, extra = score_rule(rule, fs, close_raw, scores, decisions, membership, trend, cache)
        verdicts = {c["verdict"] for c in cells.values()}
        status = "supported" if verdicts == {"supports"} else "rejected" if "contradicts" in verdicts else "testing"
        results[rule["id"]] = {"rule": rule, "status": status, "cells": cells}
        if status == "supported":
            passers[rule["id"]] = extra
        print(f"{rule['id']:34s} " + "  ".join(
            f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f}" for w, c in cells.items())
              + f"  -> {status}")

    # report-only checks for passing rules
    for rid, (targets, bench_targets, close_ff) in passers.items():
        clean = clean_prices(close_ff)
        run, bench = simulate(clean, targets, COST_BPS), simulate(clean, bench_targets, COST_BPS)
        first_hold = close_ff.index[close_ff.index.get_loc(targets.dropna(how="all").index[0]) + 1]
        results[rid]["spin_off_check"] = {w: {k: window_stats(run, bench, first_hold, *WINDOWS[w])[2][k]
                                              for k in ("net_active", "information_ratio")} for w in WINDOWS}

    commit = _git_commit()
    ledger = lookup(conn)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"scan_{stamp}.json"
    for rid, res_ in results.items():
        hid = ledger[f"Scan v1: {rid}"]
        for w, c in res_["cells"].items():
            summary = (f"factor_scan_v1 {rid} {STATUS[w]} {c['start']}..{c['end']}, 5 bps: {c['rebalances']} rebalances, "
                       f"net active {c['net_active']:.2%}/yr, IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}; "
                       f"CAGR {c['cagr']:.1%} vs benchmark {c['benchmark_cagr']:.1%}, Sharpe {c['sharpe']:.2f} vs "
                       f"{c['benchmark_sharpe']:.2f}, beta {c['beta']:.2f}, turnover {c['turnover']:.1f}x/yr; delayed fill "
                       f"net active {c['delayed_net_active']:.2%}. {c['verdict']}: {c['why']}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
        set_status(conn, hid, res_["status"])
    passed = {w: sum(r["cells"][w]["verdict"] == "supports" for r in results.values()) for w in WINDOWS}
    placebo_ok = {w: sum(r["cells"][w]["placebo"] >= BAR["placebo"] for r in results.values()) for w in WINDOWS}
    both = [rid for rid, r in results.items() if r["status"] == "supported"]
    note = (f"Round-6 scan: {len(results)} rules, {len(both)} pass both windows ({', '.join(both) or 'none'}); "
            f"passing the full bar in IS {passed['IS']} / OOS {passed['OOS']}; placebo >= 0.95 in IS {placebo_ok['IS']} / "
            f"OOS {placebo_ok['OOS']}. Hypotheses tested so far: {HYPOTHESES_BEFORE + len(results)}.")
    print(note)
    for rid in both:
        add_evidence(conn, ledger[f"Scan v1: {rid}"], "note", note, "supports")
    for w in WINDOWS:
        for rid in both:
            results[rid]["cells"][w]["_curve"].rename("equity").to_csv(OUT_DIR / f"{rid}_{w}_equity_{stamp}.csv", index_label="date")
    for r in results.values():
        for c in r["cells"].values():
            c.pop("_curve")
    path.write_text(json.dumps({"git_commit": commit, "run_at": stamp, "bar": BAR, "placebo": PLACEBO, "note": note,
                                "results": results}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
