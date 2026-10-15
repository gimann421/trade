"""Score hypotheses 126-128 of research/r13-novel-ideas-2026-10-15.md (filters on the 3-session band reversal rule).

    PYTHONPATH=. python research/round13_filters.py --register           # all eight round-13 ledger rows
    PYTHONPATH=. python research/round13_filters.py --universe all
    PYTHONPATH=. python research/round13_filters.py --universe holdout
    PYTHONPATH=. python research/round13_filters.py --finalize
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import DATA_DIR, load_bars
from core.edgar import EDGAR_DIR
from core.ledger import add_evidence, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round13_common import HYPOTHESES_BEFORE, RULES as HYPS, register, title_of
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import (BAR, COSTS, WINDOWS, break_even_bps, cleaned, dirty_index, placebo,
                                           weeks_to_confidence)
from research.round10_neighbours import MIN_AGREE, MIN_DECISIONS, load_inputs
from research.round11_ideas import judge

OUT_DIR = ROOT / "backtests" / "short_horizon_v6"
FINRA_PATH = DATA_DIR / "finra" / "shvol.csv"
WIKI_PATH = DATA_DIR / "wiki" / "views.csv"
FILINGS_PATH = EDGAR_DIR / "all_8k.csv"
SV_WINDOWS = {"IS": ("2019-01-01", "2022-12-31"), "OOS": WINDOWS["OOS"]}   # FINRA consolidated files start 2018-08


def filter_values(sh, kind, index, stocks):
    if kind == "sv":
        raw = pd.read_csv(FINRA_PATH, dtype={"Symbol": str})
        raw["Date"] = pd.to_datetime(raw["Date"].astype(str), format="%Y%m%d")
        short = raw.pivot_table(index="Date", columns="Symbol", values="ShortVolume", aggfunc="sum")
        total = raw.pivot_table(index="Date", columns="Symbol", values="TotalVolume", aggfunc="sum")
        # the files start on 2018-08-01: sessions before that have no data, so no ratio
        return sh.sv_matrix(short.reindex(columns=stocks), total.reindex(columns=stocks), index)
    if kind == "nn":
        filings = pd.read_csv(FILINGS_PATH)
        return sh.news_matrix(filings, index, stocks)
    views = pd.read_csv(WIKI_PATH, index_col=0, parse_dates=True)
    return sh.attention_matrix(views.reindex(columns=stocks), index)


def masks(kind, values, decisions, members_fn):
    """Per decision date: boolean masks over the stocks for the filtered rule (test), the coverage parent (cov)
    and the opposite half (opp)."""
    out = {v: pd.DataFrame(False, index=pd.DatetimeIndex(decisions), columns=values.columns) for v in ("test", "cov", "opp")}
    for date, cands in zip(decisions, members_fn(decisions)):
        names = [t for t in sorted(cands) if t in values.columns]
        row = values.loc[date, names]
        have = row.notna()
        if kind == "nn":
            flag = row.astype(object)
            test = have & (flag == False)       # noqa: E712  no filing in the window
            opp = have & (flag == True)         # noqa: E712
        else:
            r = row.astype(float)
            median = r.median()
            low = have & (r <= median)
            test, opp = (low, have & ~low) if kind == "sv" else (have & ~low, low)
        out["test"].loc[date, names] = test.to_numpy()
        out["cov"].loc[date, names] = have.to_numpy()
        out["opp"].loc[date, names] = opp.to_numpy()
    return out


def load_inputs_proxy(universe):
    """Daily-close stand-in for the 15:45 snapshot (used while the intraday download is incomplete): signal read at the
    close and filled at the close. Not executable; it measures the filter's effect on the same footing as its coverage parent."""
    from core.data import bars_path
    from core.intraday import sample_tickers
    from core.universe import FIRST_MONTH_END, LAST_MONTH_END, STOCK_DIR, load_member_panel, load_membership, month_end_members
    membership = load_membership()
    have = {t for t in month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END) if bars_path(t, STOCK_DIR).exists()}
    wanted = sorted({"holdout": have - set(sample_tickers()), "all": have}[universe])
    index = load_bars("VTI").index
    close = load_member_panel(wanted, "close").reindex(index)
    open_ = load_member_panel(wanted, "open").reindex(index)
    snaps = {"p1530": close, "p1545": close}
    return membership, index, close, open_, snaps, {"tickers": len(close.columns), "proxy": "daily close"}


def run(universe: str, proxy: bool = False):
    sh = load_module("short_horizon_v6")
    fs = load_module("factor_scan_v1")
    conn = connect()
    register(conn)
    membership, index, close, open_, snaps, report = (load_inputs_proxy if proxy else load_inputs)(*((universe,) if proxy else (None, universe)))
    print("data check:", json.dumps(report))
    if not proxy and min(report[f]["share_within"] for f in ("p1530", "p1545")) < MIN_AGREE:
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
    decisions = sh.decision_dates(index)
    base = {p: sh.rev5_matrix(close, snaps[p].reindex(columns=stocks)).reindex(columns=cols) for p in ("p1530", "p1545")}

    results, stamp = {}, pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    tag = "proxy_" if proxy else ""
    path = OUT_DIR / f"short_horizon_v6_{tag}{universe}_{stamp}.json"

    def evaluate(rule, variant, mask):
        windows = SV_WINDOWS if rule["filter"] == "sv" else WINDOWS
        runs, details = {}, {}
        for name, price, bps in (("primary", "p1545", 5.0), ("stress", "p1545", 10.0)) + (() if proxy else (("noisy", "p1530", 5.0),)):
            scores = base[price] if mask is None else base[price].where(mask.reindex(index).reindex(columns=cols).fillna(False).astype(bool))
            targets, detail = sh.generate_targets(rule, full, scores, decisions, members_fn)
            runs[name] = cleaned(simulate(close_ff, targets, bps), dirty)
            details[name] = detail
        held = holding_windows(details["primary"], index)
        cells = {}
        for label, (start, end) in windows.items():
            _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
            net = lambda name, b: window_stats(runs[name], bench[b], first_hold, start, end)[2]["net_active"]
            stress_active, noisy_active = net("stress", "stress"), (None if proxy else net("noisy", "primary"))
            _, pct = placebo(details["primary"], close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in held)
            extra = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
            gross = stats["net_active"] + extra * COSTS["primary"] / 1e4
            verdict, why = judge(label, n, MIN_DECISIONS[3], stats, pct, stress_active, noisy_active)
            cells[label] = {"verdict": verdict, "why": why, "decisions": n, "net_active": stats["net_active"],
                            "information_ratio": stats["information_ratio"], "placebo": pct, "gross_active": gross,
                            "annual_turnover": stats["annual_turnover"], "break_even_bps": break_even_bps(gross, extra),
                            "stress_net_active": stress_active, "noisy_net_active": noisy_active,
                            "beta": stats["beta_to_benchmark"], "start": stats["start"], "end": stats["end"]}
        whole = window_stats(runs["primary"], bench["primary"], first_hold, "2016-01-01", None)[2]
        share = float(np.mean([len(d["ranked"]) for d in details["primary"]]))
        out = {"cells": cells, "information_ratio_all": whole["information_ratio"], "net_active_all": whole["net_active"],
               "mean_ranked_names": share, "weeks_to_confidence": weeks_to_confidence(whole["information_ratio"])}
        print(f"{rule['id']:22s} {variant:6s} ranked {share:6.1f}  " + "  ".join(
            f"{w} act {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} gross {c['gross_active']:+6.1%} "
            f"turn {c['annual_turnover']:4.0f} 10bp {c['stress_net_active']:+6.1%}"
            for w, c in cells.items()) + "  -> " + "/".join(c["verdict"] for c in cells.values()), flush=True)
        return out

    results["parent"] = {"rule": sh.PARENT_RULE, "full": evaluate(sh.PARENT_RULE, "full", None)}
    for rule in sh.RULES:
        values = filter_values(sh, rule["filter"], index, stocks).reindex(columns=cols)
        m = masks(rule["filter"], values, decisions, members_fn)
        results[rule["id"]] = {"rule": rule, **{v: evaluate(rule, v, m[v]) for v in ("test", "cov", "opp")}}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ids = lookup(conn)
    for rule in sh.RULES:
        res = results[rule["id"]]
        hid = ids[title_of(rule["id"])]
        for variant, label in (("test", "filtered rule"), ("cov", "coverage parent"), ("opp", "opposite half (report only)")):
            for w, c in res[variant]["cells"].items():
                be = f"{c['break_even_bps']:.1f}" if c["break_even_bps"] is not None else "n/a"
                summary = (f"{rule['id']} {label} [{universe} universe, {report['tickers']} tickers{', daily-close proxy' if proxy else ''}] {w} {c['start']}..{c['end']}, 5 bps, 15:45 snapshot fill at the close: "
                           f"{c['decisions']} decisions, net active {c['net_active']:.2%}/yr (gross {c['gross_active']:.2%}), IR {c['information_ratio']:.2f}, "
                           f"placebo {c['placebo']:.3f}, turnover {c['annual_turnover']:.0f}x/yr, break-even {be} bps; 10 bps {c['stress_net_active']:.2%}, "
                           f"15:30 signal {c['noisy_net_active']:.2%}. {'DAILY-CLOSE PROXY (not executable). ' if proxy else ''}{c['verdict']}: {'; '.join(c['why'])}")
                add_evidence(conn, hid, "backtest", summary, c["verdict"] if variant == "test" else "inconclusive", ref=str(path.relative_to(ROOT)))
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "universe": universe, "data_check": report,
                                "bar": BAR, "costs": COSTS, "results": results}, indent=1, default=str) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def latest(universe, proxy=False):
    files = sorted(OUT_DIR.glob(f"short_horizon_v6_{'proxy_' if proxy else ''}{universe}_*.json"))
    return json.loads(files[-1].read_text()) if files else None


def finalize(proxy=False):
    sh = load_module("short_horizon_v6")
    a, h = latest("all", proxy), latest("holdout", proxy)
    conn = connect()
    ids = lookup(conn)
    passing = []
    for rule in sh.RULES:
        rid = rule["id"]
        flags = {n: all(c["verdict"] == "supports" for c in d["results"][rid]["test"]["cells"].values()) for n, d in (("all", a), ("holdout", h))}
        beats = all(d["results"][rid]["test"]["cells"][w]["net_active"] > d["results"][rid]["cov"]["cells"][w]["net_active"]
                    for d in (a, h) for w in ("IS", "OOS"))
        gross_ok = any(c["gross_active"] >= 0.04 for c in a["results"][rid]["test"]["cells"].values())
        supported = flags["all"] and flags["holdout"] and beats and gross_ok
        rejected = any(c["verdict"] == "contradicts" for d in (a, h) for c in d["results"][rid]["test"]["cells"].values())
        status = ("testing" if proxy else "supported") if supported else "rejected" if rejected else "testing"   # a proxy pass is never "supported"
        if supported:
            passing.append(rid)
        hid = ids[title_of(rid)]
        set_strategy(conn, hid, "short_horizon_v6.py")
        set_status(conn, hid, status)
        print(f"{rid:22s} all={flags['all']} holdout={flags['holdout']} beats_coverage_parent={beats} -> {status}")
    conn.close()
    print(f"Round 13 filters (126-128): {len(passing)} of {len(sh.RULES)} pass: {', '.join(passing) or 'none'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--universe", choices=["all", "holdout"])
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--proxy", action="store_true", help="daily-close signal instead of the 15:45 snapshot")
    args = parser.parse_args()
    if args.register:
        ids = register(connect())
        print(f"{len(ids)} rules registered, ids {min(ids.values())}-{max(ids.values())}")
    elif args.finalize:
        finalize(args.proxy)
    elif args.universe:
        run(args.universe, args.proxy)


if __name__ == "__main__":
    sys.exit(main())
