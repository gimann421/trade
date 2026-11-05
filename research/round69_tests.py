"""Round 69: segment focus (research/r69-segment-focus-2026-11-05.md).

    PYTHONPATH=. python research/round69_data.py facts && PYTHONPATH=. python research/round69_data.py revisions
    PYTHONPATH=. python research/round69_tests.py --register
    PYTHONPATH=. python research/round69_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.industry import load_sic
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from core.universe import members_on
from core.edgar import load_constituents
from research import round28_data, round36_data, round69_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r69-segment-focus-2026-11-05.md"
OUT_DIR = ROOT / "backtests" / "round69_tests"
MIN_SCORED = 20
START = pd.Timestamp("2017-01-31")
HYP = {"segfocus_quintile": "Holding the 20% of covered members with the highest Herfindahl index of business-segment revenue shares passes the bar in both windows against the equal-weight scored names"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 69: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 69: idea 5 of the second Opus idea pass requested by Garret 2026-11-05.",
                                        research_memo=MEMO, strategy="round69_tests.py")
    return {rid: ids[f"Round 69: {rid}"] for rid in HYP}


def focus_tables(filings, ciks):
    f = filings[filings["has_total"] | filings["hhi"].notna()].copy()
    f["score"] = np.where(f["hhi"].notna() & (f["n_seg"] >= 2), f["hhi"], 1.0)
    sym = {v: k for k, v in ciks.items()}
    f["symbol"] = f["cik"].map(sym)
    f = f.sort_values("filed")
    return {s: g[["filed", "period", "score"]].reset_index(drop=True) for s, g in f.groupby("symbol")}


def focus_at(tab, ticker, date):
    g = tab.get(ticker)
    if g is None:
        return np.nan
    ok = g[(g["filed"] < date) & (g["period"] >= date - pd.Timedelta(days=455))]
    return float(ok["score"].iloc[-1]) if len(ok) else np.nan


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
    base = pd.concat([load_facts(), round28_data.load_facts()], ignore_index=True)
    tables = base_tables(base)
    acc_tables = annual_tables()
    raw = {t: load_bars(t, round36_data.RAW) for t in stocks.columns if (round36_data.RAW / f"{t}_1Day.csv").exists()}
    adj_close = {t: stocks[t].dropna() for t in stocks.columns}
    vt = value_tables(acc_tables, tables, round36_data.load_facts(), raw, adj_close)
    filings = round69_data.load_filings()
    tab = focus_tables(filings, load_constituents())
    print("filings", len(filings), "with segments >= 2:", int((filings["n_seg"] >= 2).sum()), "members covered:", len(tab), flush=True)
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= START]
    rows = {k: [] for k in ("sf", "sf_low", "acc", "rnd", "sp")}
    cover, share = [], []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({"sf": [focus_at(tab, t, date) for t in priced]}, index=priced)
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in priced]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in priced]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in priced]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in ("sf", "acc", "rnd", "sp"):
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            picks = (list(s.index[s >= s.sort_values(ascending=False).iloc[k(len(s)) - 1]]) if key == "sf" else top(s, k(len(s)))) if ok else []
            rows[key].append((date, equal(picks) if ok else {}, list(s.index), list(s.index)))
            if key == "sf":
                low = list(s.index[s <= s.sort_values().iloc[k(len(s)) - 1]]) if ok else []
                rows["sf_low"].append((date, equal(low) if ok else {}, list(s.index), list(s.index)))
                if picks:
                    share.append(float(np.mean([t in techhealth for t in picks])))
        cover.append({"date": str(date.date()), "priced": len(priced), "sf": int(table["sf"].notna().sum()), "at_1": int((table["sf"] == 1.0).sum())})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out = {}
    actives = {k: active_series(rows[k], close_ff) for k in rows}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:7s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                      for w, c in out[name].items() if w in JUDGED), flush=True)
    corr = {k: float(actives["sf"].corr(actives[k])) for k in ("acc", "rnd", "sp")}
    print("corr (acc, rnd, sp):", {a: round(b, 2) for a, b in corr.items()})
    print("mean tech/health share of picks:", round(float(np.mean(share)), 2) if share else None)
    verdicts = {"segfocus_quintile": bar_fails(out["sf"])}
    for rid, fails in verdicts.items():
        print(rid, "PASS" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        cc = out["sf"]
        body = "; ".join(f"{w} {cc[w]['net_active']:.2%}/yr (IR {cc[w]['information_ratio']:.2f}, placebo {cc[w]['placebo']:.3f}, 10 bps {cc[w]['stress_net_active']:.2%})" for w in JUDGED)
        add_evidence(conn, ids[rid], "backtest", f"round69_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr['acc']:.2f}, R&D {corr['rnd']:.2f}, sales/price {corr['sp']:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr": corr,
                                "techhealth_share": float(np.mean(share)) if share else None, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
