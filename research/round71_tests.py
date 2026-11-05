"""Round 71: trial catalysts and recalls (research/r71-trials-recalls-2026-11-05.md).

    PYTHONPATH=. python research/round71_data.py facts && PYTHONPATH=. python research/round71_data.py revisions
    PYTHONPATH=. python research/round71_tests.py --register
    PYTHONPATH=. python research/round71_tests.py [--dry]
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
from research import round28_data, round36_data, round71_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r71-trials-recalls-2026-11-05.md"
OUT_DIR = ROOT / "backtests" / "round71_tests"
MIN_SCORED = 20
START = pd.Timestamp("2017-01-31")
HYP = {
    "pipelinesoon_quintile": "Holding the 20% of covered members with the most Phase 2 and 3 trials reaching primary completion in the next 12 months per dollar of R&D passes the bar in both windows against the equal-weight scored names",
    "norecall_basket": "Holding the covered health-care members with no matched drug or device recall in the trailing 24 months passes the bar in both windows against the equal-weight covered members",
}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 71: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 71: ideas 9 and 10 of the second Opus idea pass requested by Garret 2026-11-05.",
                                        research_memo=MEMO, strategy="round71_tests.py")
    return {rid: ids[f"Round 71: {rid}"] for rid in HYP}


def pipeline_score(trials_by, tables, ticker, date):
    t = trials_by.get(ticker)
    w = tables.get(ticker)
    if t is None or w is None:
        return np.nan
    ok = w[(w["avail"] < date) & (w.index >= date - pd.Timedelta(days=455)) & w["rnd"].notna() & (w["rnd"] > 0)]
    if ok.empty:
        return np.nan
    n = int(((t["posted"] <= date) & (t["complete"] > date) & (t["complete"] <= date + pd.Timedelta(days=365))).sum())
    return n / (float(ok["rnd"].iloc[-1]) / 1e9)


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
    trials = round71_data.load_trials()
    trials_by = {s: g for s, g in trials.groupby("symbol")}
    recalls = round71_data.load_recalls().dropna(subset=["reported"])
    recalls_by = {s: sorted(g["reported"]) for s, g in recalls.groupby("symbol")}
    sic = load_sic().astype(int)
    covered = set(sic.index[sic.isin([28, 38])])
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= START]
    rows = {k: [] for k in ("pl", "pl_low", "nr", "rc", "acc", "rnd", "sp")}
    cover = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        cov = [t for t in priced if t in covered]
        pl = pd.Series({t: pipeline_score(trials_by, tables, t, date) for t in cov if t in trials_by}).dropna()
        k = lambda n: max(1, int(round(0.2 * n)))
        ok = len(pl) >= MIN_SCORED
        rows["pl"].append((date, equal(top(pl, k(len(pl)))) if ok else {}, list(pl.index), list(pl.index)))
        rows["pl_low"].append((date, equal(top(-pl, k(len(pl)))) if ok else {}, list(pl.index), list(pl.index)))
        has = [t for t in cov if any(date - pd.Timedelta(days=730) < d <= date for d in recalls_by.get(t, []))]
        none = [t for t in cov if t not in set(has)]
        okr = len(cov) >= MIN_SCORED and len(none) >= 8
        rows["nr"].append((date, equal(none) if okr else {}, cov, cov))
        okh = len(cov) >= MIN_SCORED and len(has) >= 8
        rows["rc"].append((date, equal(has) if okh else {}, cov, cov))
        table = pd.DataFrame(index=priced)
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in priced]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in priced]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in priced]
        for key in ("acc", "rnd", "sp"):
            x = table[key].dropna()
            pk = top(x, k(len(x))) if len(x) >= 20 else []
            rows[key].append((date, equal(pk) if pk else {}, list(x.index), list(x.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), "covered": len(cov), "pipeline_scored": len(pl), "no_recall": len(none), "recall": len(has)})
    c = pd.DataFrame(cover)
    print(c.iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    print("months with >= 20 pipeline-scored names:", int((c["pipeline_scored"] >= MIN_SCORED).sum()), "of", len(c), "; max scored:", int(c["pipeline_scored"].max()), flush=True)
    out = {}
    actives = {k: active_series(rows[k], close_ff) if any(r[1] for r in rows[k]) else None for k in rows}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:7s}", "  ".join(f"{w} {c_['net_active']:+6.1%} IR {c_['information_ratio']:+5.2f} pl {c_['placebo']:.2f} 10bp {c_['stress_net_active']:+6.1%} n {c_['rebalances']}"
                                      for w, c_ in out[name].items() if w in JUDGED), flush=True)
    corr = {}
    for key in ("pl", "nr"):
        corr[key] = {k: (float(actives[key].corr(actives[k])) if actives[key] is not None else float("nan")) for k in ("acc", "rnd", "sp")}
    print("corr (acc, rnd, sp):", {a: {x: round(y, 2) for x, y in b.items()} for a, b in corr.items()})
    cols = {"pipelinesoon_quintile": "pl", "norecall_basket": "nr"}
    verdicts = {rid: bar_fails(out[cols[rid]]) for rid in HYP}
    for rid, fails in verdicts.items():
        print(rid, "PASS" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        cc = out[cols[rid]]
        body = "; ".join(f"{w} {cc[w]['net_active']:.2%}/yr (IR {cc[w]['information_ratio']:.2f}, placebo {cc[w]['placebo']:.3f}, 10 bps {cc[w]['stress_net_active']:.2%})" for w in JUDGED)
        add_evidence(conn, ids[rid], "backtest", f"round71_tests {rid}: {'passes' if not fails else 'fails'}. {body}." + (f" Fails: {'; '.join(fails)}." if fails else ""),
                     "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr": corr, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
