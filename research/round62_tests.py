"""Round 62: accrual quality and inventory mix (research/r62-accrual-quality-inventory-mix-2026-11-01-2026-10-30.md).

    PYTHONPATH=. python research/round62_data.py facts && PYTHONPATH=. python research/round62_data.py revisions
    PYTHONPATH=. python research/round62_tests.py --register
    PYTHONPATH=. python research/round62_tests.py [--dry]
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
from research import round27_data, round28_data, round36_data, round62_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r62-accrual-quality-inventory-mix-2026-11-01-2026-10-30.md"
OUT_DIR = ROOT / "backtests" / "round62_tests"
MIN_SCORED = 20
RAW = ("InventoryRawMaterialsNetOfReserves", "InventoryRawMaterials", "InventoryRawMaterialsAndSuppliesNetOfReserves", "InventoryRawMaterialsAndSupplies")
WIP = ("InventoryWorkInProcessNetOfReserves", "InventoryWorkInProcess")
FG = ("InventoryFinishedGoodsNetOfReserves", "InventoryFinishedGoods")
HYP = {
    "accrualquality_quintile": "Holding the 20% of covered members with the lowest standard deviation of Dechow-Dichev accrual residuals over their latest five usable years passes the bar in both windows against the equal-weight scored names",
    "rawshare_quintile": "Holding the 20% of covered members with the largest rise in the raw-materials share of inventory passes the bar in both windows against the equal-weight scored names",
}
COLS = {"accrualquality_quintile": "aq", "rawshare_quintile": "rs"}
EXTRAS = []


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 62: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 62: ideas 4 and 5 of the Opus idea pass requested by Garret 2026-11-01.",
                                        research_memo=MEMO, strategy="round62_tests.py")
    return {rid: ids[f"Round 62: {rid}"] for rid in HYP}


def extra_tables(facts):
    """symbol -> Series end -> raw-materials share of inventory (raw / (raw + WIP + FG)); raw and finished goods both required, WIP 0 if missing."""
    facts = facts[facts["form"].fillna("").str.startswith("10-K")].sort_values("filed")
    inst = facts[facts["start"].isna()]
    first = inst.groupby(["symbol", "tag", "end"])["val"].first()
    out = {}
    for symbol, g in first.groupby(level=0):
        by = g.droplevel(0)
        shares = {}
        for end in sorted({e for _, e in by.index}):
            def pick(tags):
                for tag in tags:
                    if (tag, end) in by.index:
                        return float(by.at[(tag, end)])
                return np.nan
            raw, wip, fg = pick(RAW), pick(WIP), pick(FG)
            if pd.notna(raw) and pd.notna(fg) and raw >= 0 and fg >= 0 and raw + fg + (0.0 if pd.isna(wip) else max(wip, 0.0)) > 0:
                shares[end] = raw / (raw + fg + (0.0 if pd.isna(wip) else max(wip, 0.0)))
        if shares:
            out[symbol] = pd.Series(shares).sort_index()
    return out


def aq_candidates(acc_tables, sic):
    """Per fiscal year with a prior and a next year: accruals and the three cash flows over assets, and when the next year's 10-K became available."""
    rows = []
    for symbol, w in acc_tables.items():
        w = w.dropna(subset=["assets", "ni", "cfo", "avail"])
        w = w[w["assets"] > 0].sort_index()
        ends = list(w.index)
        for i in range(1, len(ends) - 1):
            gap_prev, gap_next = (ends[i] - ends[i - 1]).days, (ends[i + 1] - ends[i]).days
            if not (335 <= gap_prev <= 395 and 335 <= gap_next <= 395) or symbol not in sic.index:
                continue
            y, p, n = w.iloc[i], w.iloc[i - 1], w.iloc[i + 1]
            a = y["assets"]
            rows.append({"symbol": symbol, "sic": int(sic[symbol]), "label": ends[i].year, "end": ends[i], "acc": (y["ni"] - y["cfo"]) / a,
                         "c0": p["cfo"] / a, "c1": y["cfo"] / a, "c2": n["cfo"] / a, "next_avail": n["avail"], "next_end": ends[i + 1]})
    return pd.DataFrame(rows)


def accrual_quality(cand, date):
    """symbol -> minus the standard deviation of the firm's residuals over its latest 5 usable years (3 needed), or empty."""
    usable = cand[cand["next_avail"] < date]
    resid = []
    for (_, _), g in usable.groupby(["sic", "label"]):
        if len(g) < 10:
            continue
        X = np.column_stack([np.ones(len(g)), g["c0"], g["c1"], g["c2"]])
        beta = np.linalg.lstsq(X, g["acc"].to_numpy(), rcond=None)[0]
        resid.append(pd.DataFrame({"symbol": g["symbol"].to_numpy(), "end": g["end"].to_numpy(), "next_end": g["next_end"].to_numpy(), "res": g["acc"].to_numpy() - X @ beta}))
    if not resid:
        return {}
    r = pd.concat(resid).sort_values(["symbol", "end"])
    out = {}
    for symbol, g in r.groupby("symbol"):
        last = g.tail(5)
        if len(last) >= 3 and last["next_end"].max() >= date - pd.Timedelta(days=455):
            out[symbol] = -float(last["res"].std(ddof=1))
    return out


def scores(acc_tables, extra, aqs, ticker, date):
    """aq: minus the std of accrual residuals; rs: change in the raw-materials share of inventory."""
    out = dict.fromkeys(COLS.values(), np.nan)
    if ticker in aqs:
        out["aq"] = aqs[ticker]
    wide, shares = acc_tables.get(ticker), extra.get(ticker)
    if wide is not None and shares is not None:
        ok = wide[(wide["avail"] < date) & (wide.index >= date - pd.Timedelta(days=455)) & wide["assets"].notna() & (wide["assets"] > 0)]
        if not ok.empty:
            end = ok.index[-1]
            prior = [e for e in shares.index if end - pd.Timedelta(days=395) <= e <= end - pd.Timedelta(days=335)]
            if end in shares.index and prior:
                out["rs"] = shares.at[end] - shares.at[prior[-1]]
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
    extra = extra_tables(round62_data.load_facts())
    sic = load_sic().astype(int)
    cand = aq_candidates(acc_tables, sic)
    print("names with value tables:", len(vt), "of", len(stocks.columns), flush=True)
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + EXTRAS + [k + "_high" for k in names] + ["acc", "rnd", "sp"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        aqs = accrual_quality(cand, date)
        table = pd.DataFrame({t: scores(acc_tables, extra, aqs, t, date) for t in priced}).T
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
        add_evidence(conn, ids[rid], "backtest", f"round62_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}, with sales/price {corr_sp[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "corr_with_salesprice": corr_sp, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
