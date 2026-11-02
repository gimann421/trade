"""Round 63: RPO growth, no comment letters, smoothing (research/r63-rpo-comment-letters-smoothing-2026-11-02.md).

    PYTHONPATH=. python research/round63_data.py facts && PYTHONPATH=. python research/round63_data.py revisions
    PYTHONPATH=. python research/round63_tests.py --register
    PYTHONPATH=. python research/round63_tests.py [--dry]
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
from research import round27_data, round28_data, round36_data, round63_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r63-rpo-comment-letters-smoothing-2026-11-02.md"
OUT_DIR = ROOT / "backtests" / "round63_tests"
MIN_SCORED = 20
HYP = {
    "rpogrowth_quintile": "Holding the 20% of covered members with the largest year-on-year rise in remaining performance obligations over revenue passes the bar in both windows against the equal-weight scored names",
    "nocommentletter_basket": "Holding the members with no SEC staff comment letter made public in the trailing 730 days passes the bar in both windows against the equal-weight scored names",
    "lowsmoothing_quintile": "Holding the 20% of covered members with the highest ratio of net income volatility to operating cash flow volatility passes the bar in both windows against the equal-weight scored names",
}
COLS = {"rpogrowth_quintile": "rpo", "nocommentletter_basket": "nl", "lowsmoothing_quintile": "sm"}
BASKET = {"nl"}
EXTRAS = []


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 63: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 63: ideas 7, 11 and 12 of the Opus idea pass requested by Garret 2026-11-01.",
                                        research_memo=MEMO, strategy="round63_tests.py")
    return {rid: ids[f"Round 63: {rid}"] for rid in HYP}


def rpo_tables(facts):
    """symbol -> (rpo rows[end, filed, val first-filed per end], revenue rows[end, filed, val first-filed 10-K full-year])."""
    out = {}
    rpo = facts[facts["tag"] == "RevenueRemainingPerformanceObligation"].sort_values("filed")
    rpo = rpo[rpo["start"].isna()]
    rpo = rpo.groupby(["symbol", "end"], as_index=False).first()
    rev = facts[facts["tag"].isin(["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"]) & facts["form"].fillna("").str.startswith("10-K")].copy()
    rev = rev[(rev["end"] - rev["start"]).dt.days.between(350, 380)]
    rev["pri"] = (rev["tag"] == "Revenues").astype(int)
    rev = rev.sort_values(["filed", "pri"]).groupby(["symbol", "end"], as_index=False).first()
    for symbol, g in rpo.groupby("symbol"):
        out[symbol] = (g.set_index("end").sort_index(), rev[rev["symbol"] == symbol].set_index("end").sort_index())
    return out


def rpo_score(tab, ticker, date):
    if ticker not in tab:
        return np.nan
    rpo, rev = tab[ticker]
    cur = rpo[(rpo["filed"] < date) & (rpo["filed"] >= date - pd.Timedelta(days=150))]
    if cur.empty:
        return np.nan
    end = cur.index[-1]
    prior = rpo[(rpo.index >= end - pd.Timedelta(days=395)) & (rpo.index <= end - pd.Timedelta(days=335)) & (rpo["filed"] < date)]
    r = rev[rev["filed"] < date]
    if prior.empty or r.empty or not r["val"].iloc[-1] > 0:
        return np.nan
    return float(cur["val"].iloc[-1] - prior["val"].iloc[-1]) / float(r["val"].iloc[-1])


def smoothing_score(acc_tables, ticker, date):
    wide = acc_tables.get(ticker)
    if wide is None:
        return np.nan
    ok = wide[(wide["avail"] < date) & wide["assets"].notna() & (wide["assets"] > 0) & wide["ni"].notna() & wide["cfo"].notna()]
    if ok.empty or ok.index[-1] < date - pd.Timedelta(days=455):
        return np.nan
    w = ok.tail(5)
    if len(w) < 4 or (w.index[-1] - w.index[0]).days > 5 * 400:
        return np.nan
    sc = (w["cfo"] / w["assets"]).std(ddof=1)
    return float((w["ni"] / w["assets"]).std(ddof=1) / sc) if sc > 0 else np.nan


def letter_flag(letters_by, reach, ticker, date):
    """1.0 if no letter public in the trailing 730 days, 0.0 if one, NaN if history does not reach back 850 days."""
    if ticker not in reach.index or reach[ticker] > date - pd.Timedelta(days=850):
        return np.nan
    pub = letters_by.get(ticker, [])
    return 0.0 if any(date - pd.Timedelta(days=730) < p <= date for p in pub) else 1.0


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
    rt = rpo_tables(round63_data.load_facts())
    letters = round63_data.load_letters()
    letters_by = {s: [d + pd.Timedelta(days=120) for d in g["filed"]] for s, g in letters.groupby("symbol")}
    reach = round63_data.load_reach()
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + ["nl_mirror", "sm_low", "rpo_low", "acc", "rnd", "sp"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({"rpo": [rpo_score(rt, t, date) for t in priced], "nl": [letter_flag(letters_by, reach, t, date) for t in priced],
                              "sm": [smoothing_score(acc_tables, t, date) for t in priced]}, index=priced)
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in table.index]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in table.index]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in table.index]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names + ["acc", "rnd", "sp"]:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            if key in BASKET:
                picks = list(s.index[s == 1.0]) if ok else []
                mirror = list(s.index[s == 0.0]) if ok else []
                rows["nl_mirror"].append((date, equal(mirror) if mirror else {}, list(s.index), list(s.index)))
            else:
                picks = top(s, k(len(s))) if ok else []
            rows[key].append((date, equal(picks) if picks else {}, list(s.index), list(s.index)))
            if key in share and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
            if key == "sm":
                rows["sm_low"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
            if key == "rpo":
                rows["rpo_low"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), **{key: int(table[key].notna().sum()) for key in names + ["acc", "rnd", "sp"]}})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out, corr_acc, corr_rnd, corr_sp = {}, {}, {}, {}
    acc_active, rnd_active = active_series(rows["acc"], close_ff), active_series(rows["rnd"], close_ff)
    sp_active = active_series(rows["sp"], close_ff)
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        if name in names:
            a = active_series(r, close_ff)
            corr_acc[name], corr_rnd[name], corr_sp[name] = float(a.corr(acc_active)), float(a.corr(rnd_active)), float(a.corr(sp_active))
        print(f"{name:13s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
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
        add_evidence(conn, ids[rid], "backtest", f"round63_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}, with sales/price {corr_sp[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "corr_with_salesprice": corr_sp, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
