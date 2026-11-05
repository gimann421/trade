"""Round 67: short interest (research/r67-short-interest-2026-11-05.md).

    PYTHONPATH=. python research/round67_data.py facts && PYTHONPATH=. python research/round67_data.py revisions
    PYTHONPATH=. python research/round67_tests.py --register
    PYTHONPATH=. python research/round67_tests.py [--dry]
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
from research import round28_data, round36_data, round67_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r67-short-interest-2026-11-05.md"
OUT_DIR = ROOT / "backtests" / "round67_tests"
MIN_SCORED = 20
START = pd.Timestamp("2018-07-31")
LAG = pd.Timedelta(days=12)
HYP = {
    "lowshort_quintile": "Holding the 20% of covered members with the lowest short interest as a share of shares outstanding passes the bar in both windows against the equal-weight scored names",
    "shortdrop_quintile": "Holding the 20% of covered members with the largest six-month fall in short interest over shares outstanding passes the bar in both windows against the equal-weight scored names",
    "lowacc_lowshort": "Holding the 20% of the lowest-accrual 40% of members with the lowest short interest passes the bar in both windows against the equal-weight lowest-accrual 40%",
}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 67: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 67: ideas 1, 2 and 6 of the second Opus idea pass requested by Garret 2026-11-05.",
                                        research_memo=MEMO, strategy="round67_tests.py")
    return {rid: ids[f"Round 67: {rid}"] for rid in HYP}


def si_tables(si):
    out = {}
    for symbol, g in si.sort_values("settle").drop_duplicates(["symbol", "settle"], keep="last").groupby("symbol"):
        out[symbol] = g.set_index("settle")["short"].astype(float)
    return out


def shares_table(shares_facts):
    f = shares_facts[shares_facts["tag"] == "EntityCommonStockSharesOutstanding"].sort_values("filed")
    return {s: g[["filed", "val"]].reset_index(drop=True) for s, g in f.groupby("symbol")}


def si_scores(tabs, shares, ticker, date):
    """(minus short/shares, minus the 6-month rise in short/shares) or NaNs."""
    nan = (np.nan, np.nan)
    s, sh = tabs.get(ticker), shares.get(ticker)
    if s is None or sh is None:
        return nan
    pub = s[(s.index + LAG < date) & (s.index >= date - pd.Timedelta(days=45))]
    n = sh[(sh["filed"] < date) & (sh["filed"] >= date - pd.Timedelta(days=400))]
    if pub.empty or n.empty or not n["val"].iloc[-1] > 0:
        return nan
    now_date, now = pub.index[-1], pub.iloc[-1]
    shr = float(n["val"].iloc[-1])
    level = -now / shr
    old = s[(s.index >= now_date - pd.Timedelta(days=192)) & (s.index <= now_date - pd.Timedelta(days=172))]
    drop = -(now - old.iloc[-1]) / shr if not old.empty else np.nan
    return level, drop


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
    tabs = si_tables(round67_data.load_shortint())
    shares = shares_table(round36_data.load_facts())
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= START]
    names = ["ls", "sd", "la"]
    rows = {k: [] for k in names + ["ls_high", "sd_high", "acc", "rnd", "sp"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        sc = [si_scores(tabs, shares, t, date) for t in priced]
        table = pd.DataFrame({"ls": [x[0] for x in sc], "sd": [x[1] for x in sc]}, index=priced)
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in priced]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in priced]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in priced]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in ("ls", "sd", "acc", "rnd", "sp"):
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            picks = top(s, k(len(s))) if ok else []
            rows[key].append((date, equal(picks) if ok else {}, list(s.index), list(s.index)))
            if key in share and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
            if key + "_high" in rows:
                rows[key + "_high"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        a = table["acc"].dropna()
        grp = list(top(a, max(1, int(round(0.4 * len(a)))))) if len(a) >= MIN_SCORED else []
        g = table.loc[[t for t in grp if pd.notna(table.at[t, "ls"])], "ls"]
        ok = len(g) >= MIN_SCORED
        picks = top(g, k(len(g))) if ok else []
        rows["la"].append((date, equal(picks) if ok else {}, list(g.index), list(g.index)))
        if picks:
            share["la"].append(float(np.mean([t in techhealth for t in picks])))
        cover.append({"date": str(date.date()), "priced": len(priced), "ls": int(table["ls"].notna().sum()), "sd": int(table["sd"].notna().sum()), "la_group": len(g)})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 48, 60, -1]].to_string(index=False), flush=True)
    out, corr_acc, corr_rnd, corr_sp = {}, {}, {}, {}
    acc_active, rnd_active, sp_active = (active_series(rows[k], close_ff) for k in ("acc", "rnd", "sp"))
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        if name in names:
            x = active_series(r, close_ff)
            corr_acc[name], corr_rnd[name], corr_sp[name] = float(x.corr(acc_active)), float(x.corr(rnd_active)), float(x.corr(sp_active))
        print(f"{name:8s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                      for w, c in out[name].items() if w in JUDGED), flush=True)
    print("corr with low accruals:", {k: round(v, 2) for k, v in corr_acc.items()})
    print("corr with sales/price:", {k: round(v, 2) for k, v in corr_sp.items()})
    print("corr with R&D intensity:", {k: round(v, 2) for k, v in corr_rnd.items()})
    print("mean tech/health share of picks:", {k: round(float(np.mean(v)), 2) if v else None for k, v in share.items()})
    cols = {"lowshort_quintile": "ls", "shortdrop_quintile": "sd", "lowacc_lowshort": "la"}
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
        c = out[cols[rid]]
        body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})" for w in JUDGED)
        add_evidence(conn, ids[rid], "backtest", f"round67_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[cols[rid]]:.2f}, with R&D {corr_rnd[cols[rid]]:.2f}, with sales/price {corr_sp[cols[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "corr_with_salesprice": corr_sp, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
