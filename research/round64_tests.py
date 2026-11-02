"""Round 64: opportunistic insider buys, 13F breadth, XBRL extension share, Benford (research/r64-insider-13f-xbrl-benford-2026-11-02.md).

    SEC_CONTACT=... PYTHONPATH=. python research/round64_data.py insider|fsds|f13   (plus the round25/28/36 fact files and core.industry for the reference passes)
    PYTHONPATH=. python research/round64_tests.py --register
    PYTHONPATH=. python research/round64_tests.py [--dry]
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
from research import round27_data, round28_data, round36_data, round64_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r64-insider-13f-xbrl-benford-2026-11-02.md"
OUT_DIR = ROOT / "backtests" / "round64_tests"
MIN_SCORED = 20
MIN_NAMES = 8
HYP = {
    "oppinsiderbuy_basket": "Holding every member with an opportunistic (non-routine) open-market purchase of at least $50,000 by an officer or director filed in the trailing 180 days (cash if fewer than 8) beats the equal-weight priced members in both windows (net active, IR, placebo, 10 bps)",
    "breadth_quintile": "Holding the 20% of covered members with the largest rise in 13F institutional breadth (holders gained among filers present in both quarters, usable 46 days after quarter end) passes the bar in both windows against the equal-weight scored names",
    "lowextension_quintile": "Holding the 20% of covered members whose latest 10-K has the lowest share of company-extension XBRL tags passes the bar in both windows against the equal-weight scored names",
    "benford_quintile": "Holding the 20% of covered members whose latest 10-K values deviate least from Benford's first-digit law (at least 200 values) passes the bar in both windows against the equal-weight scored names",
}
COLS = {"oppinsiderbuy_basket": "oi", "breadth_quintile": "br", "lowextension_quintile": "ex", "benford_quintile": "bf"}
BASKETS = {"oi"}
BENFORD = np.log10(1 + 1 / np.arange(1, 10))


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 64: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 64: ideas 6, 8, 9 and 10 of the Opus idea pass requested by Garret 2026-11-01 (SEC bulk data sets).",
                                        research_memo=MEMO, strategy="round64_tests.py")
    return {rid: ids[f"Round 64: {rid}"] for rid in HYP}


def insider_events(ins):
    """symbol -> sorted int days (since epoch) on which an opportunistic officer/director purchase of >= $50,000 was filed."""
    d = ins[ins["document_type"].isin(["4", "4/A"])].dropna(subset=["tdate"]).copy()
    d["ym"] = d["tdate"].dt.year * 12 + d["tdate"].dt.month - 1
    hist = {}
    for key, ym in zip(zip(d["symbol"], d["rptownercik"]), d["ym"]):
        hist.setdefault(key, set()).add(int(ym))
    p = d[(d["trans_code"] == "P") & d["rptowner_relationship"].str.contains("Officer|Director", regex=True) & (d["shares"] * d["price"] >= 50_000)]
    out = {}
    for sym, own, ym, filed in zip(p["symbol"], p["rptownercik"], p["ym"], p["filed"]):
        h = hist[(sym, own)]
        if all((int(ym) - 12 * k) in h for k in (1, 2, 3)):
            continue
        out.setdefault(sym, []).append(int(np.datetime64(filed.normalize(), "D").astype("int64")))
    return {s_: np.sort(np.array(v, dtype="int64")) for s_, v in out.items()}


def oi_score(ev, ticker, date):
    d = int(np.datetime64(date.normalize(), "D").astype("int64"))
    days = ev.get(ticker)
    if days is None:
        return 0.0
    return 1.0 if np.searchsorted(days, d, side="left") - np.searchsorted(days, d - 180, side="left") > 0 else 0.0


def breadth_tables(f13):
    """period -> {symbol: set of filer CIKs}; filer sets per period; first filing per (filer, period, symbol)."""
    f13 = f13.sort_values("filed").drop_duplicates(["CIK", "period", "symbol"])
    holders, filers = {}, {}
    for (period, symbol), g in f13.groupby(["period", "symbol"]):
        holders.setdefault(period, {})[symbol] = set(g["CIK"])
    for period, g in f13.groupby("period"):
        filers[period] = set(g["CIK"])
    return holders, filers


def br_score(tab, ticker, date):
    holders, filers = tab
    periods = sorted(p for p in holders if p + pd.Timedelta(days=46) < date and p >= date - pd.Timedelta(days=140))
    if not periods:
        return np.nan
    p = periods[-1]
    prior = [q for q in holders if 80 <= (p - q).days <= 100]
    if not prior:
        return np.nan
    q = prior[0]
    common = filers[p] & filers[q]
    if len(common) < 100:
        return np.nan
    if len(holders[p].get(ticker, set())) < 20 or len(holders[q].get(ticker, set())) < 20:
        return np.nan  # CUSIP not mapped to this member (fewer than 20 holders found): not scored
    return (len(holders[p].get(ticker, set()) & common) - len(holders[q].get(ticker, set()) & common)) / len(common)


def xbrl_tables(fs):
    """symbol -> frame of 10-K (filed, period, ext share, Benford MAD or NaN), sorted by filed."""
    d = fs.dropna(subset=["symbol"]).copy()
    d["ext"] = d["ncustom"] / d["ntags"]
    digits = d[[f"d{i}" for i in range(1, 10)]].to_numpy(dtype=float)
    n = digits.sum(axis=1)
    mad = np.abs(digits / np.where(n > 0, n, np.nan)[:, None] - BENFORD).mean(axis=1)
    d["mad"] = np.where(n >= 200, mad, np.nan)
    d.loc[d["ntags"].fillna(0) <= 0, "ext"] = np.nan
    return {s_: g.sort_values("filed")[["filed", "period", "ext", "mad"]] for s_, g in d.groupby("symbol")}


def xb_scores(xt, ticker, date):
    g = xt.get(ticker)
    if g is None:
        return np.nan, np.nan
    ok = g[(g["filed"] < date) & (g["period"] >= date - pd.Timedelta(days=455))]
    if ok.empty:
        return np.nan, np.nan
    r = ok.iloc[-1]
    return (-r["ext"] if pd.notna(r["ext"]) else np.nan), (-r["mad"] if pd.notna(r["mad"]) else np.nan)


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
    ev = insider_events(round64_data.load_insider())
    f13tab = breadth_tables(round64_data.load_f13())
    xt = xbrl_tables(round64_data.load_fsds())
    print("names with value tables:", len(vt), "of", len(stocks.columns), flush=True)
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + [k + "_high" for k in names] + ["acc", "rnd", "sp"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        xs = {t: xb_scores(xt, t, date) for t in priced}
        table = pd.DataFrame({"oi": {t: oi_score(ev, t, date) for t in priced}, "br": {t: br_score(f13tab, t, date) for t in priced},
                              "ex": {t: xs[t][0] for t in priced}, "bf": {t: xs[t][1] for t in priced}})
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in table.index]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in table.index]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in table.index]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names + ["acc", "rnd", "sp"]:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            picks = (list(s[s > 0].index) if key in BASKETS else top(s, k(len(s)))) if ok else []
            if key in BASKETS and len(picks) < MIN_NAMES:
                picks = []
            rows[key].append((date, equal(picks) if ok else {}, list(s.index), list(s.index)))
            if key in share and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
            if key + "_high" in rows:
                rows[key + "_high"].append((date, equal(list(s[s <= 0].index) if key in BASKETS else top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
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
        add_evidence(conn, ids[rid], "backtest", f"round64_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}, with sales/price {corr_sp[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "corr_with_salesprice": corr_sp, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
