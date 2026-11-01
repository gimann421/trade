"""Round 61: re-reported comparatives, deferred tax expense and bad-debt reserve build (research/r61-restate-deftax-allowance-2026-11-01-2026-10-30.md).

    PYTHONPATH=. python research/round61_data.py facts && PYTHONPATH=. python research/round61_data.py revisions
    PYTHONPATH=. python research/round61_tests.py --register
    PYTHONPATH=. python research/round61_tests.py [--dry]
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
from research import round27_data, round28_data, round36_data, round61_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r61-restate-deftax-allowance-2026-11-01-2026-10-30.md"
OUT_DIR = ROOT / "backtests" / "round61_tests"
MIN_SCORED = 20
DT1, DT2 = "DeferredIncomeTaxExpenseBenefit", "DeferredIncomeTaxesAndTaxCredits"
AL1, AL2, REC = "AccountsReceivableAllowanceForCreditLossCurrent", "AllowanceForDoubtfulAccountsReceivableCurrent", "AccountsReceivableNetCurrent"
FINANCE = set(range(60, 68))
HYP = {
    "revisionrate_quintile": "Holding the 20% of covered members with the lowest share of prior-year facts re-reported with a changed value passes the bar in both windows against the equal-weight scored names",
    "lowdeftax_quintile": "Holding the 20% of covered members with the lowest deferred income tax expense over assets passes the bar in both windows against the equal-weight scored names",
    "allowancebuild_quintile": "Holding the 20% of covered non-financial members with the largest rise in the bad-debt allowance share of gross receivables passes the bar in both windows against the equal-weight scored names",
}
COLS = {"revisionrate_quintile": "rv", "lowdeftax_quintile": "dt", "allowancebuild_quintile": "ab"}
EXTRAS = ["dx"]                                   # reported, not judged: deferred tax rule excluding SIC 60 to 67


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 61: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 61: first three ideas of the Opus idea pass (garret asked 2026-11-01).",
                                        research_memo=MEMO, strategy="round61_tests.py")
    return {rid: ids[f"Round 61: {rid}"] for rid in HYP}


def extra_tables(facts):
    """symbol -> (Series end -> deferred tax expense (flow of 350-380 days), Series end -> allowance, Series end -> net receivables), first-filed 10-K values."""
    facts = facts[facts["form"].fillna("").str.startswith("10-K")].sort_values("filed")
    dur = (facts["end"] - facts["start"]).dt.days
    flow = facts[facts["tag"].isin([DT1, DT2]) & dur.between(350, 380)]
    inst = facts[facts["start"].isna() & facts["tag"].isin([AL1, AL2, REC])]
    out = {}
    for symbol in set(flow["symbol"]) | set(inst["symbol"]):
        f, i = flow[flow["symbol"] == symbol], inst[inst["symbol"] == symbol]

        def pick(frame, first, second):
            a = frame[frame["tag"] == first].groupby("end")["val"].first()
            b = frame[frame["tag"] == second].groupby("end")["val"].first() if second else a.iloc[0:0]
            return a.combine_first(b).sort_index()

        out[symbol] = (pick(f, DT1, DT2), pick(i, AL1, AL2), pick(i, REC, None))
    return out


def rev_tables(rev):
    """symbol -> DataFrame(end, filed, rate) with at least 30 matched facts."""
    rev = rev[rev["matched"] >= round61_data.MIN_MATCHED].copy()
    rev["rate"] = rev["revised"] / rev["matched"]
    return {s: g.sort_values("filed")[["end", "filed", "rate"]].reset_index(drop=True) for s, g in rev.groupby("symbol")}


def scores(acc_tables, extra, rev, sic, ticker, date):
    """rv: -(share of prior-year facts re-reported with a changed value); dt: -(deferred tax expense / assets); ab: allowance share build.
    dx: dt without SIC 60 to 67 (report only)."""
    out = dict.fromkeys(list(COLS.values()) + EXTRAS, np.nan)
    wide = acc_tables.get(ticker)
    if wide is not None:
        ok = wide[(wide["avail"] < date) & (wide.index >= date - pd.Timedelta(days=455)) & wide["assets"].notna() & (wide["assets"] > 0)]
        ex = extra.get(ticker)
        if not ok.empty and ex is not None:
            end, r = ok.index[-1], ok.iloc[-1]
            dt, allow, rec = ex
            financial = sic.get(ticker, -1) in FINANCE
            if end in dt.index:
                out["dt"] = -dt.at[end] / r["assets"]
                if not financial:
                    out["dx"] = out["dt"]

            def share(e):
                if e in allow.index and e in rec.index and allow.at[e] >= 0 and rec.at[e] >= 0 and allow.at[e] + rec.at[e] > 0:
                    return allow.at[e] / (allow.at[e] + rec.at[e])
                return np.nan

            prior = [e for e in allow.index if end - pd.Timedelta(days=395) <= e <= end - pd.Timedelta(days=335)]
            if not financial and prior and pd.notna(share(end)) and pd.notna(share(prior[-1])) and share(prior[-1]) > 0:
                out["ab"] = share(end) - share(prior[-1])
    g = rev.get(ticker)
    if g is not None:
        ok = g[(g["filed"] < date) & (g["end"] >= date - pd.Timedelta(days=455))]
        if not ok.empty:
            out["rv"] = -float(ok["rate"].iloc[-1])
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
    extra = extra_tables(round61_data.load_facts())
    rev = rev_tables(round61_data.load_revisions())
    print("names with value tables:", len(vt), "of", len(stocks.columns), flush=True)
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + EXTRAS + [k + "_high" for k in names] + ["acc", "rnd", "sp"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores(acc_tables, extra, rev, sic, t, date) for t in priced}).T
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in table.index]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in table.index]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in table.index]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names + EXTRAS + ["acc", "rnd", "sp"]:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            picks = top(s, k(len(s))) if ok else []
            rows[key].append((date, equal(picks) if ok else {}, list(s.index), list(s.index)))
            if key in share and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
            if key + "_high" in rows:
                rows[key + "_high"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), **{key: int(table[key].notna().sum()) for key in names + EXTRAS + ["acc", "rnd", "sp"]}})
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
        add_evidence(conn, ids[rid], "backtest", f"round61_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}, with sales/price {corr_sp[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "corr_with_salesprice": corr_sp, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
