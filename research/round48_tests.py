"""Round 48: 8-K event types (research/r48-eightk-event-types-2026-10-30.md).

    PYTHONPATH=. python research/round36_data.py shares && PYTHONPATH=. python research/round36_data.py raw && PYTHONPATH=. python research/round48_data.py
    PYTHONPATH=. python research/round48_tests.py --register
    PYTHONPATH=. python research/round48_tests.py [--dry]
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
from research import round27_data, round28_data, round36_data, round44_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from as base_tables
from research.round36_tests import value_tables, scores as sp_scores
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r48-eightk-event-types-2026-10-30.md"
OUT_DIR = ROOT / "backtests" / "round48_tests"
MIN_SCORED = 20
DISTRESS = {"1.02", "1.03", "2.04", "2.05", "2.06", "3.01", "4.01", "4.02"}
HYP = {
    "nodistress_quintile": "Holding every scored name with none of the distress-type 8-K items (1.02, 1.03, 2.04, 2.05, 2.06, 3.01, 4.01, 4.02) in the trailing 365 days beats the equal-weight scored names in both windows (net active, IR, placebo, 10 bps)",
    "noacquirer_quintile": "Holding every scored name with no completed-acquisition 8-K (item 2.01) in the trailing 730 days beats the equal-weight scored names in both windows (net active, IR, placebo, 10 bps)",
    "nonewdebt_quintile": "Holding every scored name with no direct-financial-obligation 8-K (item 2.03) in the trailing 365 days beats the equal-weight scored names in both windows (net active, IR, placebo, 10 bps)",
}
COLS = {"nodistress_quintile": "nd", "noacquirer_quintile": "na", "nonewdebt_quintile": "nb"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 48: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 48: 8-K event types, keep testing until more pass.",
                                        research_memo=MEMO, strategy="round48_tests.py")
    return {rid: ids[f"Round 48: {rid}"] for rid in HYP}


def event_tables(filings):
    """symbol -> (sorted filing days of all 8-Ks, per-class flags aligned: distress, 2.01, 2.03)."""
    k = filings[filings["form"] == "8-K"].sort_values("filed")
    out = {}
    for s_, g in k.groupby("symbol"):
        sets = [set(str(x).split(",")) for x in g["items"].fillna("")]
        out[s_] = (g["filed"].dt.normalize().values.astype("datetime64[D]").astype("int64"),
                   np.array([bool(x & DISTRESS) for x in sets]), np.array(["2.01" in x for x in sets]), np.array(["2.03" in x for x in sets]))
    return out


def scores(et, ticker, date):
    """1.0 if the name had none of the event class in the window (picked), 0.0 if it had any; scored only with >= 6 8-Ks in the file."""
    out = dict.fromkeys(COLS.values(), np.nan)
    t = et.get(ticker)
    if t is None or len(t[0]) < 6:
        return out
    days, dis, acq, debt = t
    d = int(np.datetime64(date.normalize(), "D").astype("int64"))
    hi = np.searchsorted(days, d, side="right")
    lo1, lo2 = np.searchsorted(days, d - 365, side="right"), np.searchsorted(days, d - 730, side="right")
    out["nd"] = 0.0 if dis[lo1:hi].any() else 1.0
    out["na"] = 0.0 if acq[lo2:hi].any() else 1.0
    out["nb"] = 0.0 if debt[lo1:hi].any() else 1.0
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
    et = event_tables(round44_data.load_filings())
    print("names with value tables:", len(vt), "of", len(stocks.columns), flush=True)
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values())
    rows = {k: [] for k in names + [k + "_high" for k in names] + ["acc", "rnd", "sp"]}
    cover, share = [], {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores(et, t, date) for t in priced}).T
        table["sp"] = [sp_scores(vt, adj_close, t, date)["sp"] for t in table.index]
        table["acc"] = [scores_at(acc_tables, t, date)[1] for t in table.index]
        table["rnd"] = [rnd_scores(tables, t, date)["rnd"] for t in table.index]
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names + ["acc", "rnd", "sp"]:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            picks = (list(s[s > 0].index) if key in names else top(s, k(len(s)))) if ok else []
            rows[key].append((date, equal(picks) if ok else {}, list(s.index), list(s.index)))
            if key in share and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
            if key + "_high" in rows:
                rows[key + "_high"].append((date, equal(list(s[s <= 0].index) if key in names else top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
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
        add_evidence(conn, ids[rid], "backtest", f"round48_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr_acc[COLS[rid]]:.2f}, with R&D {corr_rnd[COLS[rid]]:.2f}, with sales/price {corr_sp[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr_acc,
                                "corr_with_rnd": corr_rnd, "corr_with_salesprice": corr_sp, "techhealth_share": {k: float(np.mean(v)) if v else None for k, v in share.items()},
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
