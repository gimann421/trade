"""Round 24: dividend month premium, dividend growth, dividend payers (research/r24-dividends-2026-10-20.md).

    PYTHONPATH=. python research/round24_data.py
    PYTHONPATH=. python research/round24_tests.py --register
    PYTHONPATH=. python research/round24_tests.py [--dry]
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
from core.universe import members_on
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round24_data import load_dividends
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r24-dividends-2026-10-20.md"
OUT_DIR = ROOT / "backtests" / "round24_tests"
MIN_NAMES = 20
HYP = {
    "divmonth_predicted": "Holding S&P 500 members that paid a regular dividend in the same calendar month a year earlier passes the bar in both windows",
    "divgrowth_quintile": "Holding the 20% of dividend payers with the highest year-on-year dividend growth passes the bar in both windows",
    "payers_tilt": "Holding S&P 500 members that paid at least three regular dividends in the past 400 days passes the bar in both windows",
}
KEY = {"divmonth_predicted": "pred", "divgrowth_quintile": "growth", "payers_tilt": "payers"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 24: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 24: dividend data from Alpaca corporate actions, keep testing until one passes.",
                                        research_memo=MEMO, strategy="round24_tests.py")
    return {rid: ids[f"Round 24: {rid}"] for rid in HYP}


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
    div = load_dividends()
    div = div[~div["special"].astype(bool)].sort_values("ex_date")
    by_symbol = {s: (g["ex_date"].to_numpy(dtype="datetime64[ns]"), g["rate"].to_numpy(float)) for s, g in div.groupby("symbol")}
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    rows = {k: [] for k in ("pred", "notpred", "growth", "cut", "payers", "nonpayers")}
    cover = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        nxt = date + pd.offsets.MonthBegin(1)
        lo, hi = nxt - pd.DateOffset(years=1), nxt + pd.offsets.MonthEnd(0) - pd.DateOffset(years=1)
        d64 = np.datetime64(date)
        pred, payers, growth = [], [], {}
        for t in priced:
            if t not in by_symbol:
                continue
            ex, rate = by_symbol[t]
            known = ex <= d64
            if (known & (ex >= np.datetime64(lo)) & (ex <= np.datetime64(hi))).any():
                pred.append(t)
            if (known & (ex > d64 - np.timedelta64(400, "D"))).sum() >= 3:
                payers.append(t)
            ex_k, rate_k = ex[known], rate[known]
            if len(ex_k) >= 5 and (d64 - ex_k[-1]) <= np.timedelta64(135, "D"):
                gap = (ex_k[-1] - ex_k[-5]).astype("timedelta64[D]").astype(int)
                if 330 <= gap <= 400 and rate_k[-5] > 0:
                    growth[t] = rate_k[-1] / rate_k[-5] - 1
        g = pd.Series(growth, dtype=float)
        k20 = lambda n: max(1, int(round(0.2 * n)))
        tilt = lambda names: equal(names) if len(names) >= MIN_NAMES else equal(priced)
        rows["pred"].append((date, tilt(pred), priced, priced))
        rows["notpred"].append((date, tilt([t for t in priced if t not in set(pred)]), priced, priced))
        rows["growth"].append((date, equal(top(g, k20(len(g)))) if len(g) >= MIN_NAMES else equal(priced), list(g.index) if len(g) >= MIN_NAMES else priced, priced))
        rows["cut"].append((date, equal(top(-g, k20(len(g)))) if len(g) >= MIN_NAMES else equal(priced), list(g.index) if len(g) >= MIN_NAMES else priced, priced))
        rows["payers"].append((date, tilt(payers), priced, priced))
        rows["nonpayers"].append((date, tilt([t for t in priced if t not in set(payers)]), priced, priced))
        cover.append({"date": str(date.date()), "priced": len(priced), "predicted": len(pred), "payers": len(payers), "growth_scored": len(g)})
    cov = pd.DataFrame(cover)
    print(cov.iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out = {}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:9s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                      for w, c in out[name].items() if w in JUDGED), flush=True)
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
        add_evidence(conn, ids[rid], "backtest", f"round24_tests {rid}: {'passes' if not fails else 'fails'}. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
