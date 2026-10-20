"""Round 20: recent index additions, residual skewness, lottery-day maximum, quiet volume build-up
(research/r20-index-adds-skew-max-quiet-volume-2026-10-20.md).

    PYTHONPATH=. python research/round20_tests.py --register
    PYTHONPATH=. python research/round20_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from core.universe import load_member_panel, load_membership, members_on
from research.round6_scan import load_inputs, load_module, lookup
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top

MEMO = "research/r20-index-adds-skew-max-quiet-volume-2026-10-20.md"
OUT_DIR = ROOT / "backtests" / "round20_tests"
HYP = {
    "recent_adds": "Holding S&P 500 members added to the index within the previous 126 days passes the bar in both windows against the equal-weight members",
    "resskew_low_quintile": "Holding the 20% of members with the lowest 12-1 residual return skewness passes the bar in both windows",
    "max_low_quintile": "Holding the 20% of members with the lowest best-day return of the past month passes the bar in both windows",
    "quietvol_third": "Holding members in the top third by 21/252-session volume ratio and the bottom third by absolute 21-session return passes the bar in both windows",
}
KEY = {"recent_adds": "adds", "resskew_low_quintile": "skew_low", "max_low_quintile": "max_low", "quietvol_third": "quiet"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 20: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 20: thread-chosen ideas, keep testing until one passes.",
                                        research_memo=MEMO, strategy="round20_tests.py")
    return {rid: ids[f"Round 20: {rid}"] for rid in HYP}


def additions(membership):
    """ticker -> list of change dates on which it joined after at least 365 days of absence."""
    adds, last_in, prev = {}, {}, frozenset()
    for date, members in membership.items():
        for t in members - prev:
            if t not in last_in or (date - last_in[t]).days > 365:
                adds.setdefault(t, []).append(date)
        for t in members:
            last_in[t] = date
        prev = members
    return adds


def residual_skew(rm, returns, factors, t_pos, tickers, start_lag=252, end_lag=21, min_valid=231):
    y, f = rm._window(returns[tickers], factors, t_pos, start_lag, end_lag)
    if y is None:
        return pd.Series(dtype=float)
    valid = y.notna()
    y = y.loc[:, valid.sum() >= min_valid]
    valid = valid.loc[:, y.columns]
    x = np.column_stack([np.ones(len(f)), f.to_numpy()])
    out = {}
    for t in y.columns:
        m = valid[t].to_numpy()
        yy, xx = y[t].to_numpy()[m], x[m]
        beta = np.linalg.lstsq(xx, yy, rcond=None)[0]
        resid = yy - xx[:, 1:] @ beta[1:]
        sd = resid.std(ddof=0)
        if sd > 0:
            out[t] = float(((resid - resid.mean()) ** 3).mean() / sd ** 3)
    return pd.Series(out, dtype=float)


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
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    close_ff = stocks.ffill()
    returns = stocks.pct_change(fill_method=None)
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    volume = load_member_panel(list(stocks.columns), "volume").reindex(index)[stocks.columns]
    adds = additions(membership)
    vr = volume.rolling(21, min_periods=19).mean() / volume.rolling(252, min_periods=200).mean()
    mx = returns.rolling(21, min_periods=19).max()
    move = (stocks / stocks.shift(21) - 1).abs()
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    rows = {k: [] for k in ("adds", "not_adds", "skew_low", "skew_high", "max_low", "max_high", "quiet", "loud")}
    counts = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        t_pos = index.get_loc(date)
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        k = lambda n, frac: max(1, int(round(frac * n)))
        recent = [t for t in priced if any(0 <= (date - a).days <= 126 for a in adds.get(t, []))]
        counts.append(len(recent))
        rows["adds"].append((date, equal(recent) if len(recent) >= 5 else {}, priced, priced))
        rest = [t for t in priced if t not in set(recent)]
        rows["not_adds"].append((date, equal(rest) if len(recent) >= 5 else {}, priced, priced))
        sk = residual_skew(rm, returns, factors, t_pos, priced)
        rows["skew_low"].append((date, equal(top(-sk, k(len(sk), 0.2))), list(sk.index), priced))
        rows["skew_high"].append((date, equal(top(sk, k(len(sk), 0.2))), list(sk.index), priced))
        m = mx.loc[date, priced].dropna()
        rows["max_low"].append((date, equal(top(-m, k(len(m), 0.2))), list(m.index), priced))
        rows["max_high"].append((date, equal(top(m, k(len(m), 0.2))), list(m.index), priced))
        both = pd.DataFrame({"v": vr.loc[date, priced], "m": move.loc[date, priced]}).replace([np.inf, -np.inf], np.nan).dropna()
        hi_v, lo_m, hi_m = both["v"] >= both["v"].quantile(2 / 3), both["m"] <= both["m"].quantile(1 / 3), both["m"] >= both["m"].quantile(2 / 3)
        quiet, loud = list(both.index[hi_v & lo_m]), list(both.index[hi_v & hi_m])
        rows["quiet"].append((date, equal(quiet) if len(quiet) >= 5 else {}, list(both.index), priced))
        rows["loud"].append((date, equal(loud) if len(loud) >= 5 else {}, list(both.index), priced))
    print("recent additions per decision: min", min(counts), "median", int(np.median(counts)), "max", max(counts), flush=True)
    out = {}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:10s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} "
                                       f"10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}" for w, c in out[name].items()), flush=True)
    verdicts = {rid: bar_fails(out[KEY[rid]]) for rid in HYP}
    for rid, fails in verdicts.items():
        print(rid, "PASS" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        c = out[KEY[rid]]
        body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})" for w in JUDGED)
        add_evidence(conn, ids[rid], "backtest", f"round20_tests {rid}: {'passes' if not fails else 'fails'}. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "results": out, "verdicts": verdicts,
                                "recent_additions": counts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
