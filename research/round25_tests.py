"""Round 25: gross profitability, low accruals, low asset growth and a quality composite (research/r25-quality-2026-10-20.md).

    PYTHONPATH=. python research/round25_data.py
    PYTHONPATH=. python research/round25_tests.py --register
    PYTHONPATH=. python research/round25_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from core.universe import members_on
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r25-quality-2026-10-20.md"
OUT_DIR = ROOT / "backtests" / "round25_tests"
MIN_SCORED = 20
HYP = {
    "gp_assets_quintile": "Holding the 20% of covered members with the highest gross profit over assets passes the bar in both windows against the equal-weight scored names",
    "lowaccruals_quintile": "Holding the 20% of covered members with the lowest accruals over assets passes the bar in both windows against the equal-weight scored names",
    "lowassetgrowth_quintile": "Holding the 20% of covered members with the lowest asset growth passes the bar in both windows against the equal-weight scored names",
    "quality_composite_quintile": "Holding the 20% of covered members with the best average rank of profitability, accruals and asset growth passes the bar in both windows against the equal-weight scored names",
}
KEY = {"gp_assets_quintile": "gp", "lowaccruals_quintile": "acc", "lowassetgrowth_quintile": "ag", "quality_composite_quintile": "qual"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 25: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 25: annual SEC fundamentals (quality), keep testing until one passes.",
                                        research_memo=MEMO, strategy="round25_tests.py")
    return {rid: ids[f"Round 25: {rid}"] for rid in HYP}


def annual_tables():
    """symbol -> DataFrame(end, gp, assets, ni, cfo, avail) of first-filed annual 10-K values, one row per fiscal year end with all of
    assets, ni, cfo (gp may be NaN: it is required only by the profitability tests)."""
    facts = load_facts()
    facts = facts[facts["form"].fillna("").str.startswith("10-K")].sort_values("filed")
    dur = (facts["end"] - facts["start"]).dt.days
    flow = facts[dur.between(350, 380)]
    inst = facts[facts["start"].isna() & (facts["tag"] == "Assets")]
    keep = pd.concat([flow, inst])
    first = keep.groupby(["symbol", "tag", "end"], as_index=False).first()
    tables = {}
    for symbol, g in first.groupby("symbol"):
        wide = g.pivot(index="end", columns="tag", values="val")
        avail = g.groupby("end")["filed"].max()
        wide["avail"] = avail
        wide = wide.rename(columns={"GrossProfit": "gp", "Assets": "assets", "NetIncomeLoss": "ni", "NetCashProvidedByUsedInOperatingActivities": "cfo"})
        for c in ("gp", "assets", "ni", "cfo"):
            if c not in wide:
                wide[c] = np.nan
        tables[symbol] = wide.sort_index()
    return tables


def scores_at(tables, ticker, date):
    """(gp/assets, -accruals, -asset growth) or NaNs for the latest usable fiscal year."""
    wide = tables.get(ticker)
    nan = (np.nan, np.nan, np.nan)
    if wide is None:
        return nan
    ok = wide[(wide["avail"] < date) & (wide.index >= date - pd.Timedelta(days=455)) & wide["assets"].notna() & (wide["assets"] > 0)]
    if ok.empty:
        return nan
    end = ok.index[-1]
    r = ok.iloc[-1]
    gp = r["gp"] / r["assets"] if pd.notna(r["gp"]) else np.nan
    acc = -(r["ni"] - r["cfo"]) / r["assets"] if pd.notna(r["ni"]) and pd.notna(r["cfo"]) else np.nan
    prior = wide[(wide.index >= end - pd.Timedelta(days=395)) & (wide.index <= end - pd.Timedelta(days=335)) & wide["assets"].notna() & (wide["assets"] > 0)]
    ag = -(r["assets"] / prior["assets"].iloc[-1] - 1) if len(prior) else np.nan
    return gp, acc, ag


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
    tables = annual_tables()
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    rows = {k: [] for k in ("gp", "gp_low", "acc", "acc_high", "ag", "ag_high", "qual", "qual_low")}
    cover = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores_at(tables, t, date) for t in priced}, index=["gp", "acc", "ag"]).T
        k = lambda n: max(1, int(round(0.2 * n)))
        for key, col in (("gp", "gp"), ("acc", "acc"), ("ag", "ag")):
            s = table[col].dropna()
            ok = len(s) >= MIN_SCORED
            rows[key].append((date, equal(top(s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
            rows[key + ("_low" if key == "gp" else "_high")].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        full = table.dropna()
        ok = len(full) >= MIN_SCORED
        comp = full.rank(pct=True).mean(axis=1) if ok else pd.Series(dtype=float)
        rows["qual"].append((date, equal(top(comp, k(len(comp)))) if ok else {}, list(full.index), list(full.index)))
        rows["qual_low"].append((date, equal(top(-comp, k(len(comp)))) if ok else {}, list(full.index), list(full.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), "gp": int(table["gp"].notna().sum()), "acc": int(table["acc"].notna().sum()),
                      "ag": int(table["ag"].notna().sum()), "all3": len(full)})
    cov = pd.DataFrame(cover)
    print(cov.iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out = {}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:9s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                      for w, c in out[name].items() if w in JUDGED), flush=True)
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
        add_evidence(conn, ids[rid], "backtest", f"round25_tests {rid}: {'passes' if not fails else 'fails'}. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
