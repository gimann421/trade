"""Tests 2 and 4 of round 14: two branches of the residual momentum decile rule.

    PYTHONPATH=. python research/round14_momentum.py --register
    PYTHONPATH=. python research/round14_momentum.py --check      # coverage numbers only
    PYTHONPATH=. python research/round14_momentum.py
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.ledger import add_evidence, connect, set_status
from core.portfolio import month_ends
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on,
                           month_end_members)
from research.round14_common import MEMO, register, title_of
from research.round14_data import load_shares
from research.round6_scan import BAR, WINDOWS, judge, load_inputs, load_module, lookup, score_rule

OUT_DIR = ROOT / "backtests" / "round14_momentum"
WEIGHT_1M, HIGH_SHARE, FIP_POOL, FIP_KEEP = 0.5, 0.30, 0.30, 1 / 3
FORMATION = {"start_lag": 126, "end_lag": 21, "min_valid": 105}
RECENT_DAYS, RECENT_MIN = 21, 15


def residual_parts(returns, factors, t_pos, tickers, p=FORMATION):
    """Per ticker: formation residual score (the parent's), FIP, and the residual score of the last 21 sessions
    (betas from the formation window). Same data rule as strategies/residual_momentum_v1.residual_scores."""
    lo, hi = max(t_pos - p["start_lag"], 0), t_pos - p["end_lag"]
    f = factors.iloc[lo:hi + 1]
    ok = ~f.isna().any(axis=1).to_numpy()
    f_form = f.fillna(0.0).to_numpy()
    y_all = returns[tickers].iloc[lo:hi + 1].to_numpy()
    f_recent = factors.iloc[t_pos - RECENT_DAYS + 1:t_pos + 1].fillna(0.0).to_numpy()
    y_recent = returns[tickers].iloc[t_pos - RECENT_DAYS + 1:t_pos + 1].to_numpy()
    x = np.column_stack([np.ones(len(f_form)), f_form])
    out = {}
    for j, t in enumerate(tickers):
        y = y_all[:, j]
        m = ~np.isnan(y) & ok
        if m.sum() < p["min_valid"]:
            continue
        beta = np.linalg.lstsq(x[m], y[m], rcond=None)[0]
        resid = y[m] - x[m][:, 1:] @ beta[1:]
        sd = resid.std(ddof=1)
        if not sd > 0:
            continue
        sign = np.sign(np.prod(1 + resid) - 1)
        fip = sign * ((resid < 0).mean() - (resid > 0).mean())
        yr = y_recent[:, j]
        r_ok = ~np.isnan(yr)
        res1 = np.nan
        if r_ok.sum() >= RECENT_MIN:
            rr = yr[r_ok] - f_recent[r_ok] @ beta[1:]
            s1 = rr.std(ddof=1)
            res1 = rr.mean() / s1 if s1 > 0 else np.nan
        out[t] = (resid.mean() / sd, fip, res1)
    return pd.DataFrame(out, index=["res6", "fip", "res1"]).T


def shares_lookup(shares):
    table = {}
    for symbol, g in shares.groupby("symbol"):
        g = g.drop_duplicates("filed", keep="last").sort_values("filed")
        table[symbol] = (g["filed"].to_numpy(), g["shares"].to_numpy(dtype=float))
    return table


def shares_at(table, ticker, date):
    if ticker not in table:
        return np.nan
    filed, vals = table[ticker]
    k = np.searchsorted(filed, np.datetime64(date), side="right") - 1
    return vals[k] if k >= 0 else np.nan


def z(s):
    return (s - s.mean()) / s.std(ddof=1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    conn = connect()
    ids = register(conn)
    if args.register:
        print(f"registered {ids}")
        return
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    wanted = list(stocks.columns)
    volume = load_member_panel(wanted, "volume").reindex(index)[wanted]
    vol21 = volume.rolling(RECENT_DAYS, min_periods=RECENT_MIN).sum()
    table = shares_lookup(load_shares())
    decisions = index[month_ends(index)]
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    returns = stocks.pct_change(fill_method=None)
    start_date = pd.Timestamp(fs.FIRST_DECISION)
    base = pd.DataFrame(np.nan, index, stocks.columns)
    sttm, fip_scores = base.copy(), base.copy()
    cover, checks = [], []
    for date in [d for d in decisions if d >= start_date]:
        members = members_on(membership, [date])[0]
        t_pos = index.get_loc(date)
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        parts = residual_parts(returns, factors, t_pos, priced)
        if parts.empty:
            continue
        # the parent score must equal the vectorised one used in round 6 and the shadow record
        ref = rm.residual_scores(returns, factors, t_pos, priced, **fs.RESMOM6_1)
        both = parts["res6"].reindex(ref.index)
        checks.append(float((both - ref).abs().max()))
        base.loc[date, parts.index] = parts["res6"].to_numpy()
        turn = pd.Series({t: vol21.at[date, t] / shares_at(table, t, date) for t in parts.index}).replace([np.inf, -np.inf], np.nan)
        have = turn.dropna()
        high = set(have.index[have.rank(pct=True, ascending=True) > 1 - HIGH_SHARE]) if len(have) >= 20 else set()
        cover.append({"date": str(date.date()), "ranked": len(parts), "with_turnover": len(have), "high": len(high)})
        s = z(parts["res6"])
        add = z(parts["res1"].fillna(parts["res1"].median()))
        sttm.loc[date, parts.index] = (s + WEIGHT_1M * add * pd.Series([t in high for t in parts.index], index=parts.index)).to_numpy()
        pool = parts["res6"].rank(ascending=False, method="first") <= max(1, int(round(FIP_POOL * len(parts))))
        keep_n = max(1, int(round(0.1 * len(parts))))
        pool_fip = parts.loc[pool, "fip"].sort_values()
        chosen = list(pool_fip.index[:keep_n])
        # chosen names get scores far above everyone else's; the parent z-score orders the rest
        fs_row = z(parts["res6"]).copy()
        fs_row[chosen] = 100.0 - pool_fip[chosen].rank(method="first")
        fip_scores.loc[date, parts.index] = fs_row.to_numpy()
    print(f"parent score check: max abs difference {max(checks):.2e} over {len(checks)} months")
    cov = pd.DataFrame(cover)
    print(f"coverage: median ranked {cov.ranked.median():.0f}, with turnover {cov.with_turnover.median():.0f} "
          f"({(cov.with_turnover / cov.ranked).median():.0%}), high-turnover {cov.high.median():.0f}")
    if args.check:
        return
    stock_close = stocks.copy()
    stock_close[fs.CASH] = etf[fs.CASH]
    for m in (base, sttm, fip_scores):
        m[fs.CASH] = np.nan
    cache, results = {}, {}
    rules = {"stock_resmom6_1_decile": ("parent", base), "resmom_sttm_decile": ("new", sttm), "resmom_fip_decile": ("new", fip_scores)}
    for rid, (kind, scores) in rules.items():
        rule = {"id": rid, "family": "stock", "signal": rid, "fraction": 0.1, "trend": False}
        cells, _ = score_rule(rule, fs, stock_close, scores, decisions, membership, None, cache)
        for c in cells.values():
            c.pop("_curve", None)
        results[rid] = {"kind": kind, "cells": cells}
        print(rid, "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} "
                              f"turn {c['turnover']:.1f}" for w, c in cells.items()), flush=True)
    parent = results["stock_resmom6_1_decile"]["cells"]
    for rid, res in results.items():
        if res["kind"] == "parent":
            continue
        verdicts = {}
        for w, c in res["cells"].items():
            beats = c["net_active"] > parent[w]["net_active"]
            if c["verdict"] == "supports" and not beats:
                c["verdict"], c["why"] = "contradicts", f"passes the bar but net active {c['net_active']:.2%} does not exceed the parent's {parent[w]['net_active']:.2%}"
            elif c["verdict"] == "contradicts" and beats:
                c["why"] += f"; (beats the parent's {parent[w]['net_active']:.2%})"
            verdicts[w] = c["verdict"]
        res["status"] = "supported" if set(verdicts.values()) == {"supports"} else \
            "rejected" if "contradicts" in verdicts.values() else "testing"

    # how different are the books?
    overlap = {}
    for rid, scores in (("resmom_sttm_decile", sttm), ("resmom_fip_decile", fip_scores)):
        rule = {"family": "stock", "fraction": 0.1, "trend": False}
        _, _, d_new = fs.generate_targets(rule, stock_close, scores, decisions, membership, None)
        _, _, d_old = fs.generate_targets(rule, stock_close, base, decisions, membership, None)
        shares_ = [len(set(a["picks"]) & set(b["picks"])) / max(1, len(b["picks"])) for a, b in zip(d_new, d_old)]
        overlap[rid] = float(np.mean(shares_))
    print("mean overlap of picks with the parent:", overlap)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"momentum_{stamp}.json"
    ledger_ids = lookup(conn)
    for rid, res in results.items():
        if res["kind"] == "parent":
            continue
        hid = ledger_ids[title_of(rid)]
        for w, c in res["cells"].items():
            p = parent[w]
            summary = (f"round14_momentum {rid} {w} {c['start']}..{c['end']}, 5 bps: {c['rebalances']} rebalances, net active "
                       f"{c['net_active']:.2%}/yr, IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}, turnover {c['turnover']:.1f}x/yr; "
                       f"parent resmom decile {p['net_active']:.2%}, IR {p['information_ratio']:.2f}; mean pick overlap with parent {overlap[rid]:.0%}. "
                       f"{c['verdict']}: {c['why']}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
        set_status(conn, hid, res["status"])
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "bar": BAR, "coverage": cover, "overlap": overlap,
                                "parent_score_check_max_abs_diff": max(checks), "results": results}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
