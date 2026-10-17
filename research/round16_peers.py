"""Test 3 of round 16: rank by the 5-day return of the five most correlated peers minus the stock's own.

    PYTHONPATH=. python research/round16_peers.py --register
    PYTHONPATH=. python research/round16_peers.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.intraday import sample_tickers
from core.ledger import add_evidence, connect, set_status
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on,
                           month_end_members)
from research.round15_filters import judge_cell
from research.round16_common import MEMO, RULES, register, title_of
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import WINDOWS, break_even_bps, cleaned, dirty_index, placebo
from research.round9_executable import load_inputs

OUT_DIR = ROOT / "backtests" / "round16_peers"
FIRST_DECISION = "2017-01-03"
HOLD, RULE_ID = 3, "rev5_h3_band40_s"
MIN_DECISIONS = {"IS": 160, "OOS": 100}
LOOKBACK, MIN_COMMON, N_PEERS = 250, 200, 5


def pairwise_corr(x: np.ndarray) -> np.ndarray:
    """Pearson correlation between all column pairs, using only days where both are valid (NaN allowed);
    pairs with fewer than MIN_COMMON common days get NaN."""
    v = (~np.isnan(x)).astype(float)
    z = np.nan_to_num(x)
    n = v.T @ v
    sx = z.T @ v                      # sx[i, j] = sum of x_i over days both valid
    sxy = z.T @ z
    sxx = (z ** 2).T @ v
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy - sx * sx.T / n
        var = sxx - sx ** 2 / n
        corr = cov / np.sqrt(var * var.T)
    corr[n < MIN_COMMON] = np.nan
    np.fill_diagonal(corr, np.nan)
    return corr


def peer_lists(close, membership, decisions):
    """decision date -> (names, peer positions per name): the N_PEERS names with the highest correlation of
    market-adjusted daily returns over the previous LOOKBACK sessions (ending the session before the decision date)."""
    index = close.index
    ret = close.pct_change(fill_method=None)
    adj = ret.sub(ret.mean(axis=1), axis=0)
    out = {}
    for d in decisions:
        pos = index.get_loc(d)
        if pos < LOOKBACK + 1:
            continue
        members = members_on(membership, [d])[0]
        names = [t for t in close.columns if t in members and pd.notna(close.at[d, t])]
        if len(names) < 30:
            continue
        corr = pairwise_corr(adj.iloc[pos - LOOKBACK:pos][names].to_numpy())
        filled = np.where(np.isnan(corr), -2.0, corr)
        peers = np.argpartition(-filled, N_PEERS, axis=1)[:, :N_PEERS]
        ok = np.take_along_axis(filled, peers, axis=1) > -2.0
        out[d] = (names, np.where(ok, peers, -1))
    return out


def peer_scores(price, close, peers_by_date, own_sign=True):
    """(peerlag, peers_only) score matrices: mean peer 5-day return minus own, and mean peer 5-day return alone."""
    r5 = (price / close.shift(5) - 1)
    lag = pd.DataFrame(np.nan, close.index, close.columns)
    only = lag.copy()
    for d, (names, peers) in peers_by_date.items():
        r = r5.loc[d, names].to_numpy(dtype=float)
        pr = np.where(peers >= 0, r[np.where(peers >= 0, peers, 0)], np.nan)
        with np.errstate(all="ignore"):
            mean_peer = np.nanmean(pr, axis=1)
        mean_peer[np.isnan(pr).all(axis=1)] = np.nan
        lag.loc[d, names] = mean_peer - r
        only.loc[d, names] = mean_peer
    return lag, only


def evaluate(label, close, snaps, sh, fs, membership, variants, decisions, bench_targets, first_hold, dirty, rule):
    index = close.index
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    members_fn = lambda dates: members_on(membership, dates)
    bench = {name: cleaned(simulate(close_ff, bench_targets, bps), dirty) for name, bps in {"5": 5.0, "10": 10.0}.items()}
    peers_by_date = peer_lists(close, membership, [d for d in decisions if d >= pd.Timestamp(FIRST_DECISION)])
    cache = {}
    for variant, price_name, bps in variants:
        price = close if price_name == "close" else snaps[price_name].reindex(index=index, columns=close.columns)
        parent = -(price / close.shift(5) - 1)
        lag, only = peer_scores(price, close, peers_by_date)
        for m in (parent, lag, only):
            m[sh.CASH] = np.nan
        cache[variant] = {"parent": parent, "peerlag": lag, "peers_only": only}
    results = {}
    for unit in ("parent", "peerlag", "peers_only"):
        runs, details = {}, {}
        for variant, price_name, bps in variants:
            targets, detail = sh.generate_targets(rule, full, cache[variant][unit], None, decisions, members_fn)
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
        print(label, f"{unit:11s}", "  ".join(
            f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%}"
            + (f" 1530 {c['noisy_net_active']:+6.1%}" if c["noisy_net_active"] is not None else "") + f" turn {c['turnover']:4.0f} n {c['decisions']}"
            for w, c in cells.items()), flush=True)
    return results


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
    cells = {}
    for ev, needs_noisy in (("screen_all", False), ("screen_unseen", False), ("snapshot", True)):
        for w in WINDOWS:
            v, why = judge_cell(out[ev]["peerlag"][w], out[ev]["parent"][w], MIN_DECISIONS[w], needs_noisy)
            cells[f"{ev}/{w}"] = {"verdict": v, "why": why}
    vs = {c["verdict"] for c in cells.values()}
    status = "supported" if vs == {"supports"} else "rejected" if "contradicts" in vs else "testing"
    print("verdict:", status)
    for k, c in cells.items():
        print("   ", k, c["verdict"], "; ".join(c["why"]))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"peers_{stamp}.json"
    hid = lookup(conn)[title_of("peerlag_h3_band40_s")]
    for ev in ("screen_all", "screen_unseen", "snapshot"):
        for w in WINDOWS:
            c, p, m = out[ev]["peerlag"][w], out[ev]["parent"][w], out[ev]["peers_only"][w]
            cell = cells[f"{ev}/{w}"]
            summary = (f"round16_peers peerlag_h3_band40_s {ev} {w} {c['start']}..{c['end']}, 5 bps: {c['decisions']} decisions, net active "
                       f"{c['net_active']:.2%}/yr, IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}, 10 bps {c['stress_net_active']:.2%}"
                       + (f", 15:30 signal {c['noisy_net_active']:.2%}" if c["noisy_net_active"] is not None else "")
                       + f", turnover {c['turnover']:.0f}x; parent {p['net_active']:.2%} (IR {p['information_ratio']:.2f}); peers-only signal {m['net_active']:.2%} "
                       f"(IR {m['information_ratio']:.2f}). {cell['verdict']}: {'; '.join(cell['why'])}")
            add_evidence(conn, hid, "backtest", summary, cell["verdict"], ref=str(path.relative_to(ROOT)))
    set_status(conn, hid, status)
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "first_decision": FIRST_DECISION,
                                "results": out, "cells": cells, "verdict": status}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
