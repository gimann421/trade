"""Round 34: stock compensation, restructuring, R&D plus stock compensation (research/r34-sbc-restructuring-2026-10-29.md).

    PYTHONPATH=. python research/round34_data.py
    PYTHONPATH=. python research/round34_tests.py --register
    PYTHONPATH=. python research/round34_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.industry import load_sic
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from core.universe import members_on
from research import round28_data, round34_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r34-sbc-restructuring-2026-10-29.md"
OUT_DIR = ROOT / "backtests" / "round34_tests"
MIN_SCORED = 20
SBC, RST = "ShareBasedCompensation", "RestructuringCharges"
HYP = {
    "sbc_quintile": "Holding the 20% of covered members with the highest stock compensation over assets passes the bar in both windows against the equal-weight scored names",
    "lowrestructuring_quintile": "Holding the 20% of covered members with the lowest restructuring charges over assets passes the bar in both windows against the equal-weight scored names",
    "rnd_sbc_quintile": "Holding the 20% of covered members with the highest R&D plus stock compensation over assets passes the bar in both windows and beats the R&D quintile",
}
COLS = {"sbc_quintile": "sbc", "lowrestructuring_quintile": "rst", "rnd_sbc_quintile": "rsbc"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 34: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 34: intangible-investment and earnings-quality neighbours, keep testing until more pass.",
                                        research_memo=MEMO, strategy="round34_tests.py")
    return {rid: ids[f"Round 34: {rid}"] for rid in HYP}


def extra_tables(facts):
    """symbol -> DataFrame(end -> sbc, rst) of first-filed 10-K values; has_rst marks symbols with any restructuring fact."""
    facts = facts[facts["form"].fillna("").str.startswith("10-K")].sort_values("filed")
    dur = (facts["end"] - facts["start"]).dt.days
    first = facts[dur.between(350, 380)].groupby(["symbol", "tag", "end"], as_index=False).first()
    out = {}
    for symbol, g in first.groupby("symbol"):
        wide = g.pivot(index="end", columns="tag", values="val")
        for c in (SBC, RST):
            if c not in wide:
                wide[c] = np.nan
        out[symbol] = pd.DataFrame({"sbc": wide[SBC], "rst": wide[RST]}).sort_index()
        out[symbol].attrs["has_rst"] = bool(wide[RST].notna().any())
    return out


def scores(tables, extra, ticker, date):
    out = dict.fromkeys(COLS.values(), np.nan)
    base = tables.get(ticker)
    if base is None:
        return out
    ok = base[(base["avail"] < date) & (base.index >= date - pd.Timedelta(days=455)) & (base["assets"] > 0)]
    if ok.empty:
        return out
    end, r = ok.index[-1], ok.iloc[-1]
    a = r["assets"]
    ex = extra.get(ticker)
    sbc = np.nan
    if ex is not None and end in ex.index:
        e = ex.loc[end]
        sbc = e["sbc"]
        if pd.notna(sbc) and sbc > 0:
            out["sbc"] = sbc / a
        if pd.notna(e["rst"]):
            out["rst"] = -e["rst"] / a
        elif ex.attrs.get("has_rst"):
            out["rst"] = 0.0
    if pd.notna(r["rnd"]) and r["rnd"] > 0:
        out["rsbc"] = (r["rnd"] + (sbc if pd.notna(sbc) and sbc > 0 else 0.0)) / a
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
    extra = extra_tables(round34_data.load_facts())
    acc_tables = annual_tables()
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + [k + "_high" for k in names] + ["acc", "rnd"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores(tables, extra, t, date) for t in priced}).T
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
    for w in JUDGED:       # 211 is a branch off the R&D rule on the same names: it must also beat the parent's information ratio
        if not out["rsbc"][w]["information_ratio"] > out["rnd"][w]["information_ratio"]:
            verdicts["rnd_sbc_quintile"].append(f"{w} IR {out['rsbc'][w]['information_ratio']:.2f} not above the R&D quintile's {out['rnd'][w]['information_ratio']:.2f}")
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
        add_evidence(conn, ids[rid], "backtest", f"round34_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
