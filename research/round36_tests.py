"""Round 36: classic value yields (research/r36-value-yields-2026-10-29.md).

    PYTHONPATH=. python research/round36_data.py shares && PYTHONPATH=. python research/round36_data.py raw
    PYTHONPATH=. python research/round36_tests.py --register
    PYTHONPATH=. python research/round36_tests.py [--dry]
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
from research import round27_data, round28_data, round36_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r36-value-yields-2026-10-29.md"
OUT_DIR = ROOT / "backtests" / "round36_tests"
MIN_SCORED = 20
HYP = {
    "bookprice_quintile": "Holding the 20% of covered members with the highest book value over market value passes the bar in both windows against the equal-weight scored names",
    "earnprice_quintile": "Holding the 20% of covered members with the highest earnings over market value (positive earnings) passes the bar in both windows against the equal-weight scored names",
    "cfprice_quintile": "Holding the 20% of covered members with the highest operating cash flow over market value passes the bar in both windows against the equal-weight scored names",
    "salesprice_quintile": "Holding the 20% of covered members with the highest revenue over market value passes the bar in both windows against the equal-weight scored names",
}
COLS = {"bookprice_quintile": "bp", "earnprice_quintile": "ep", "cfprice_quintile": "cp", "salesprice_quintile": "sp"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 36: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 36: classic value yields, keep testing until more pass.",
                                        research_memo=MEMO, strategy="round36_tests.py")
    return {rid: ids[f"Round 36: {rid}"] for rid in HYP}


def value_tables(annual, base, shares, raw, adj_close):
    """symbol -> DataFrame(end -> avail, book, ni, cfo, rev, mv0 (market value at filing), adj0 (adjusted close at filing))."""
    rev = pd.concat([f for f in [round27_data.load_facts()] if f is not None], ignore_index=True)
    rev = rev[rev["tag"].isin(["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"]) & rev["form"].fillna("").str.startswith("10-K")]
    rev = rev[(rev["end"] - rev["start"]).dt.days.between(350, 380)].sort_values("filed")
    revf = rev.groupby(["symbol", "end", "tag"], as_index=False).first()
    revf = revf.sort_values("tag", ascending=False).groupby(["symbol", "end"]).first()["val"]  # prefer Revenues
    sh = shares[shares["form"].fillna("").str.startswith("10-K")]
    cover = sh[sh["tag"] == "EntityCommonStockSharesOutstanding"].sort_values("filed")
    dil = sh[sh["tag"] != "EntityCommonStockSharesOutstanding"]
    dil = dil[(dil["end"] - dil["start"]).dt.days.between(350, 380)].sort_values("filed").groupby(["symbol", "end"], as_index=False).first()
    out = {}
    for symbol, a in annual.items():
        b = base.get(symbol)
        if b is None or symbol not in raw or symbol not in adj_close:
            continue
        rows = []
        for end, r in a.iterrows():
            if pd.isna(r["avail"]) or end not in b.index or pd.isna(b.at[end, "liab"]) or pd.isna(r["assets"]):
                continue
            d = dil[(dil["symbol"] == symbol) & (dil["end"] == end)]
            c = cover[(cover["symbol"] == symbol) & (cover["filed"] == r["avail"])]
            n = d["val"].iloc[0] if len(d) else np.nan
            cv = c["val"].max() if len(c) else np.nan
            n_use = cv if pd.notna(cv) and (pd.isna(n) or cv >= 0.5 * n) else n
            px = raw[symbol]["close"]
            adj = adj_close[symbol]
            pos = px.index.searchsorted(r["avail"])
            if pd.isna(n_use) or pos >= len(px) or (px.index[pos] - r["avail"]).days > 5 or px.index[pos] not in adj.index:
                continue
            rows.append({"end": end, "avail": r["avail"], "book": r["assets"] - b.at[end, "liab"], "ni": r["ni"], "cfo": r["cfo"],
                         "rev": revf.get((symbol, end), np.nan), "assets": r["assets"], "mv0": n_use * px.iloc[pos], "adj0": adj.loc[px.index[pos]]})
        if rows:
            out[symbol] = pd.DataFrame(rows).set_index("end").sort_index()
    return out


def scores(vt, adj_close, ticker, date):
    out = dict.fromkeys(COLS.values(), np.nan)
    t = vt.get(ticker)
    if t is None or date not in adj_close[ticker].index:
        return out
    ok = t[(t["avail"] < date) & (t.index >= date - pd.Timedelta(days=455))]
    if ok.empty:
        return out
    r = ok.iloc[-1]
    mv = r["mv0"] * adj_close[ticker].loc[date] / r["adj0"]
    if not mv > 0:
        return out
    out["bp"] = r["book"] / mv
    if pd.notna(r["ni"]) and r["ni"] > 0:
        out["ep"] = r["ni"] / mv
    out["cp"] = r["cfo"] / mv if pd.notna(r["cfo"]) else np.nan
    out["sp"] = r["rev"] / mv if pd.notna(r["rev"]) else np.nan
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
    print("names with value tables:", len(vt), "of", len(stocks.columns), flush=True)
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + [k + "_high" for k in names] + ["acc", "rnd"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores(vt, adj_close, t, date) for t in priced}).T
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in table.index]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in table.index]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names + ["acc", "rnd"]:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            picks = top(s, k(len(s))) if ok else []
            rows[key].append((date, equal(picks) if ok else {}, list(s.index), list(s.index)))
            if key in share and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
            if key + "_high" in rows:
                rows[key + "_high"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), **{key: int(table[key].notna().sum()) for key in names + ["acc", "rnd"]}})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out, corr_acc, corr_rnd = {}, {}, {}
    acc_active, rnd_active = active_series(rows["acc"], close_ff), active_series(rows["rnd"], close_ff)
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        if name in names:
            a = active_series(r, close_ff)
            corr_acc[name], corr_rnd[name] = float(a.corr(acc_active)), float(a.corr(rnd_active))
        print(f"{name:13s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                       for w, c in out[name].items() if w in JUDGED), flush=True)
    print("corr with low accruals:", {k: round(v, 2) for k, v in corr_acc.items()})
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
        add_evidence(conn, ids[rid], "backtest", f"round36_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
