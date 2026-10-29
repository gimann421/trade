"""Round 33: recent splits, spin-off parents, special dividends (research/r33-corporate-actions-2026-10-29.md).

    PYTHONPATH=. python research/round33_data.py
    PYTHONPATH=. python research/round33_tests.py --register
    PYTHONPATH=. python research/round33_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.industry import load_sic
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from core.universe import members_on
from research import round33_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule
from research.round24_data import load_dividends
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r33-corporate-actions-2026-10-29.md"
OUT_DIR = ROOT / "backtests" / "round33_tests"
MIN_NAMES = 8
HYP = {
    "recent_split_basket": "Holding all members with a forward split in the previous 365 days (at least 8, else cash) passes the bar in both windows against the equal-weight priced members",
    "spinoff_parent_basket": "Holding all members that spun off a unit in the previous 730 days (at least 8, else cash) passes the bar in both windows against the equal-weight priced members",
    "special_dividend_basket": "Holding all members that paid a special dividend in the previous 365 days (at least 8, else cash) passes the bar in both windows against the equal-weight priced members",
}
KEY = {"recent_split_basket": "split", "spinoff_parent_basket": "spin", "special_dividend_basket": "special"}
WINDOW_DAYS = {"split": 365, "spin": 730, "special": 365}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 33: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 33: corporate-action events, keep testing until more pass.",
                                        research_memo=MEMO, strategy="round33_tests.py")
    return {rid: ids[f"Round 33: {rid}"] for rid in HYP}


def event_tables():
    splits, spins = round33_data.load_events()
    div = load_dividends()
    special = div[div["special"].astype(bool)]
    return {"split": splits[["symbol", "ex_date"]], "spin": spins[["symbol", "ex_date"]], "special": special[["symbol", "ex_date"]]}


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
    events = event_tables()
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    rows = {k: [] for k in KEY.values()}
    sizes = {k: [] for k in KEY.values()}
    share = {k: [] for k in KEY.values()}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        for key, ev in events.items():
            recent = ev[(ev["ex_date"] <= date) & (ev["ex_date"] > date - pd.Timedelta(days=WINDOW_DAYS[key]))]["symbol"]
            names = sorted(set(recent) & set(priced))
            sizes[key].append(len(names))
            on = len(names) >= MIN_NAMES
            rows[key].append((date, equal(names) if on else {}, priced, priced))
            if on:
                share[key].append(float(np.mean([t in techhealth for t in names])))
    out = {}
    for key, r in rows.items():
        out[key] = run_rule(r, close_ff, index)
        print(f"{key:8s} basket size median {np.median(sizes[key]):.0f} (months on {sum(s >= MIN_NAMES for s in sizes[key])} of {len(sizes[key])}); tech/health share {np.mean(share[key]) if share[key] else float('nan'):.2f}")
        print("   ", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                              for w, c in out[key].items() if w in JUDGED), flush=True)
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
        add_evidence(conn, ids[rid], "backtest", f"round33_tests {rid}: {'passes' if not fails else 'fails'}. {body}; basket size median {np.median(sizes[KEY[rid]]):.0f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "basket_sizes": sizes, "results": out, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
