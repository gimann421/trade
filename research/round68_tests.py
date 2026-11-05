"""Round 68: lobbying spend (research/r68-lobbying-2026-11-05.md).

    PYTHONPATH=. python research/round68_data.py facts && PYTHONPATH=. python research/round68_data.py revisions
    PYTHONPATH=. python research/round68_tests.py --register
    PYTHONPATH=. python research/round68_tests.py [--dry]
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
from research import round28_data, round36_data, round63_data, round68_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r68-lobbying-2026-11-05.md"
OUT_DIR = ROOT / "backtests" / "round68_tests"
MIN_SCORED = 20
START = pd.Timestamp("2017-01-31")
HYP = {
    "lobbyintensity_quintile": "Holding the 20% of covered members with the highest lobbying spend over revenue passes the bar in both windows against the equal-weight scored names",
    "lobbygrowth_quintile": "Holding the 20% of covered members with the fastest year-on-year growth in lobbying spend passes the bar in both windows against the equal-weight scored names",
}
COLS = {"lobbyintensity_quintile": "li", "lobbygrowth_quintile": "lg"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 68: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 68: ideas 3 and 4 of the second Opus idea pass requested by Garret 2026-11-05.",
                                        research_memo=MEMO, strategy="round68_tests.py")
    return {rid: ids[f"Round 68: {rid}"] for rid in HYP}


def quarterly_spend(filings):
    """symbol -> DataFrame(qend, posted, spend): latest filing per (registrant, year, quarter), spend = expenses else income."""
    f = filings.copy()
    f["q"] = f["period"].map({"first_quarter": 1, "second_quarter": 2, "third_quarter": 3, "fourth_quarter": 4})
    f = f.dropna(subset=["q"])
    f["spend"] = f["expenses"].fillna(f["income"]).fillna(0.0)
    f["qend"] = pd.to_datetime(dict(year=f["year"], month=(f["q"] * 3).astype(int), day=1)) + pd.offsets.MonthEnd(0)
    out = {}
    for symbol, g in f.groupby("symbol"):
        rows = []
        for (reg, y, q), h in g.sort_values("posted").groupby(["registrant_id", "year", "q"]):
            # version history: each filing replaces the previous from its posted date on
            for _, r in h.iterrows():
                rows.append((r["qend"], r["registrant_id"], r["posted"], r["spend"]))
        out[symbol] = pd.DataFrame(rows, columns=["qend", "reg", "posted", "spend"])
    return out


def spend_window(t, date, end_lo, end_hi):
    """Total spend of quarters ending in (end_lo, end_hi], using for each (registrant, quarter) the latest filing posted before date."""
    x = t[(t["posted"] < date) & (t["qend"] > end_lo) & (t["qend"] <= end_hi)]
    if x.empty:
        return 0.0
    return float(x.sort_values("posted").groupby(["reg", "qend"])["spend"].last().sum())


def revenue_table(facts):
    rev = facts[facts["tag"].isin(["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"]) & facts["form"].fillna("").str.startswith("10-K")].copy()
    rev = rev[(rev["end"] - rev["start"]).dt.days.between(350, 380)]
    rev["pri"] = (rev["tag"] == "Revenues").astype(int)
    rev = rev.sort_values(["filed", "pri"]).groupby(["symbol", "end"], as_index=False).first()
    return {s: g.set_index("end").sort_index() for s, g in rev.groupby("symbol")}


def scores(sp_, rv, ticker, date):
    out = {"li": np.nan, "lg": np.nan}
    t = sp_.get(ticker)
    if t is None:
        return out
    hi = date - pd.Timedelta(days=20)
    top_ = (hi - pd.offsets.QuarterEnd(0)) if hi == hi + pd.offsets.QuarterEnd(0) else hi - pd.offsets.QuarterEnd(1)
    top_ = pd.Timestamp(top_).normalize()
    lo = top_ - pd.Timedelta(days=365)
    now = spend_window(t, date, lo, top_)
    prior = spend_window(t, date, lo - pd.Timedelta(days=365), top_ - pd.Timedelta(days=365))
    r = rv.get(ticker)
    if r is not None:
        ok = r[(r["filed"] < date) & (r.index >= date - pd.Timedelta(days=455))]
        if not ok.empty and ok["val"].iloc[-1] > 0:
            out["li"] = now / float(ok["val"].iloc[-1])
    if prior >= 200000:
        out["lg"] = now / prior - 1
    return out


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
    filings = round68_data.load_filings()
    sp_ = quarterly_spend(filings)
    rv = revenue_table(round63_data.load_facts())
    print("members with lobbying filings:", len(sp_), "of", filings["symbol"].nunique(), flush=True)
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= START]
    names = list(COLS.values())
    rows = {k: [] for k in names + ["li_ind", "li_low", "lg_low", "acc", "rnd", "sp"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores(sp_, rv, t, date) for t in priced}).T
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in table.index]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in table.index]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in table.index]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names + ["acc", "rnd", "sp"]:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            picks = top(s, k(len(s))) if ok else []
            rows[key].append((date, equal(picks) if ok else {}, list(s.index), list(s.index)))
            if key in share and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
            if key == "li":
                rows["li_low"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
                ranks = s.groupby(sic.reindex(s.index).values).rank(pct=True)
                ranks = ranks[sic.reindex(s.index).groupby(sic.reindex(s.index)).transform("size").values >= 3]
                oki = len(ranks) >= MIN_SCORED
                rows["li_ind"].append((date, equal(top(ranks, k(len(ranks)))) if oki else {}, list(ranks.index), list(ranks.index)))
            if key == "lg":
                rows["lg_low"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), **{key: int(table[key].notna().sum()) for key in names + ["acc", "rnd", "sp"]}})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out, corr_acc, corr_rnd, corr_sp = {}, {}, {}, {}
    acc_active, rnd_active, sp_active = (active_series(rows[k], close_ff) for k in ("acc", "rnd", "sp"))
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        if name in names + ["li_ind"]:
            x = active_series(r, close_ff)
            corr_acc[name], corr_rnd[name], corr_sp[name] = float(x.corr(acc_active)), float(x.corr(rnd_active)), float(x.corr(sp_active))
        print(f"{name:8s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                      for w, c in out[name].items() if w in JUDGED), flush=True)
    print("corr with low accruals:", {k: round(v, 2) for k, v in corr_acc.items()})
    print("corr with sales/price:", {k: round(v, 2) for k, v in corr_sp.items()})
    print("corr with R&D intensity:", {k: round(v, 2) for k, v in corr_rnd.items()})
    print("mean tech/health share of picks:", {k: round(float(np.mean(v)), 2) if v else None for k, v in share.items()})
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
        add_evidence(conn, ids[rid], "backtest", f"round68_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}, with sales/price {corr_sp[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "corr_with_salesprice": corr_sp, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
