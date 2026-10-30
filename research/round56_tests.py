"""Round 56: replication of the three passes in the S&P 600 (research/r56-midsmall-replication-2026-10-30.md).

    PYTHONPATH=. python research/round56_data.py constituents && python research/round56_data.py facts && python research/round56_data.py bars
    PYTHONPATH=. python research/round56_tests.py --register
    PYTHONPATH=. python research/round56_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from research import round27_data, round36_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_tests import annual_tables, scores_at
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round56_data import OUT, load_constituents_map
from research.round6_scan import lookup

MEMO = "research/r56-midsmall-replication-2026-10-30.md"
OUT_DIR = ROOT / "backtests" / "round56_tests"
MIN_SCORED = 20
FIRST_DECISION = "2017-01-31"
HYP = {
    "smallcap_lowaccruals": "Holding the 20% of current S&P 600 members with the lowest accruals over assets passes the bar in both windows against the equal-weight scored names",
    "smallcap_rnd": "Holding the 20% of current S&P 600 members with the highest R&D over assets passes the bar in both windows against the equal-weight scored names",
    "smallcap_salesprice": "Holding the 20% of current S&P 600 members with the highest sales over market value passes the bar in both windows against the equal-weight scored names",
}
COLS = {"smallcap_lowaccruals": "acc", "smallcap_rnd": "rnd", "smallcap_salesprice": "sp"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 56: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 56: replication of the three passes in a new universe.",
                                        research_memo=MEMO, strategy="round56_tests.py")
    return {rid: ids[f"Round 56: {rid}"] for rid in HYP}


def read(name):
    return pd.read_csv(OUT / name / "facts.csv", parse_dates=["start", "end", "filed"])


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
    symbols = sorted(load_constituents_map())
    index = load_bars("VTI").index
    adj = {t: load_bars(t, OUT / "bars")["close"] for t in symbols if (OUT / "bars" / f"{t}_1Day.csv").exists()}
    raw = {t: load_bars(t, OUT / "raw") for t in symbols if (OUT / "raw" / f"{t}_1Day.csv").exists()}
    stocks = pd.DataFrame(adj).reindex(index)
    close_ff = stocks.ffill()
    adj_close = {t: stocks[t].dropna() for t in stocks.columns}
    f25, f27, f28, shares = read("r25"), read("r27"), read("r28"), read("shares")
    acc_tables = annual_tables(f25)
    tables = base_tables(pd.concat([f25, f28], ignore_index=True))
    round27_data.load_facts = lambda: f27
    vt = value_tables(acc_tables, tables, shares, raw, adj_close)
    print("priced symbols:", len(stocks.columns), "of", len(symbols), "| value tables:", len(vt), flush=True)
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + [k + "_high" for k in names]}
    cover = []
    for date in decisions:
        priced = [t for t in stocks.columns if pd.notna(stocks.at[date, t])]
        table = pd.DataFrame(index=priced)
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in priced]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in priced]
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in priced]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            rows[key].append((date, equal(top(s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
            rows[key + "_high"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), **{key: int(table[key].notna().sum()) for key in names}})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out = {}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:10s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                       for w, c in out[name].items() if w in JUDGED), flush=True)
    verdicts = {rid: bar_fails(out[COLS[rid]]) for rid in HYP}
    for rid, fails in verdicts.items():
        print(rid, "PASS" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        c = out[COLS[rid]]
        body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})" for w in JUDGED)
        add_evidence(conn, ids[rid], "backtest", f"round56_tests {rid}: {'replicates' if not fails else 'does not replicate'} in the S&P 600. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
