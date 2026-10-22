"""Round 27: receivables and inventory build-ups (research/r27-working-capital-2026-10-22.md).

    PYTHONPATH=. python research/round27_data.py
    PYTHONPATH=. python research/round27_tests.py --register
    PYTHONPATH=. python research/round27_tests.py [--dry]
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
from research import round27_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables
from research.round26_tests import active_series
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r27-working-capital-2026-10-22.md"
OUT_DIR = ROOT / "backtests" / "round27_tests"
MIN_SCORED = 20
AR, INV = "AccountsReceivableNetCurrent", "InventoryNet"
REV = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax")
HYP = {
    "lowdar_quintile": "Holding the 20% of covered members with the lowest receivables increase over assets passes the bar in both windows against the equal-weight scored names",
    "lowdinv_quintile": "Holding the 20% of covered members with the lowest inventory increase over assets passes the bar in both windows against the equal-weight scored names",
    "lowexcessar_quintile": "Holding the 20% of covered members with the lowest receivables growth minus revenue growth passes the bar in both windows against the equal-weight scored names",
}
COLS = {"lowdar_quintile": "dar", "lowdinv_quintile": "dinv", "lowexcessar_quintile": "xar"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 27: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 27: working-capital parts of accruals, keep testing until more pass.",
                                        research_memo=MEMO, strategy="round27_tests.py")
    return {rid: ids[f"Round 27: {rid}"] for rid in HYP}


def balance_tables(facts):
    """symbol -> DataFrame(end -> assets, ar, inv, rev, avail) of first-filed 10-K values."""
    facts = facts[facts["form"].fillna("").str.startswith("10-K")].sort_values("filed")
    dur = (facts["end"] - facts["start"]).dt.days
    keep = pd.concat([facts[dur.between(350, 380)], facts[facts["start"].isna() & facts["tag"].isin(["Assets", AR, INV])]])
    first = keep.groupby(["symbol", "tag", "end"], as_index=False).first()
    tables = {}
    for symbol, g in first.groupby("symbol"):
        wide = g.pivot(index="end", columns="tag", values="val")
        for c in ("Assets", AR, INV) + REV:
            if c not in wide:
                wide[c] = np.nan
        out = pd.DataFrame({"assets": wide["Assets"], "ar": wide[AR], "inv": wide[INV], "rev": wide[REV[0]].fillna(wide[REV[1]])})
        out["avail"] = g[g["tag"] == "Assets"].groupby("end")["filed"].max()
        tables[symbol] = out.dropna(subset=["assets", "avail"]).sort_index()
    return tables


def scores(tables, ticker, date):
    out = dict.fromkeys(COLS.values(), np.nan)
    wide = tables.get(ticker)
    if wide is None:
        return out
    ok = wide[(wide["avail"] < date) & (wide.index >= date - pd.Timedelta(days=455)) & (wide["assets"] > 0)]
    if ok.empty:
        return out
    end, r = ok.index[-1], ok.iloc[-1]
    prior = wide[(wide.index >= end - pd.Timedelta(days=395)) & (wide.index <= end - pd.Timedelta(days=335))]
    if prior.empty:
        return out
    p = prior.iloc[-1]
    if pd.notna(r["ar"]) and pd.notna(p["ar"]):
        out["dar"] = -(r["ar"] - p["ar"]) / r["assets"]
        if p["ar"] > 0 and pd.notna(r["rev"]) and pd.notna(p["rev"]) and p["rev"] > 0:
            out["xar"] = -((r["ar"] / p["ar"] - 1) - (r["rev"] / p["rev"] - 1))
    if pd.notna(r["inv"]) and pd.notna(p["inv"]):
        out["dinv"] = -(r["inv"] - p["inv"]) / r["assets"]
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
    tables = balance_tables(pd.concat([load_facts(), round27_data.load_facts()], ignore_index=True))
    acc_tables = annual_tables()
    from research.round25_tests import scores_at
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + [k + "_high" for k in names] + ["acc"]}
    cover = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores(tables, t, date) for t in priced}).T
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in table.index]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names + ["acc"]:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            rows[key].append((date, equal(top(s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
            if key != "acc":
                rows[key + "_high"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), **{key: int(table[key].notna().sum()) for key in names + ["acc"]}})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out, corr = {}, {}
    acc_active = active_series(rows["acc"], close_ff)
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        if name in names:
            corr[name] = float(active_series(r, close_ff).corr(acc_active))
        print(f"{name:12s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                      for w, c in out[name].items() if w in JUDGED), flush=True)
    print("corr with low accruals:", {k: round(v, 2) for k, v in corr.items()})
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
        add_evidence(conn, ids[rid], "backtest", f"round27_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
