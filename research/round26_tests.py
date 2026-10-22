"""Round 26: cash flow over assets, ROA change, low capex, free cash flow (research/r26-cashflow-fundamentals-2026-10-22.md).

    PYTHONPATH=. python research/round26_data.py
    PYTHONPATH=. python research/round26_tests.py --register
    PYTHONPATH=. python research/round26_tests.py [--dry]
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
from research import round26_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r26-cashflow-fundamentals-2026-10-22.md"
OUT_DIR = ROOT / "backtests" / "round26_tests"
MIN_SCORED = 20
CAPEX = "PaymentsToAcquirePropertyPlantAndEquipment"
HYP = {
    "cfo_assets_quintile": "Holding the 20% of covered members with the highest operating cash flow over assets passes the bar in both windows against the equal-weight scored names",
    "droa_quintile": "Holding the 20% of covered members with the largest rise in net income over assets passes the bar in both windows against the equal-weight scored names",
    "lowcapex_quintile": "Holding the 20% of covered members with the lowest capex over assets passes the bar in both windows against the equal-weight scored names",
    "fcf_assets_quintile": "Holding the 20% of covered members with the highest free cash flow over assets passes the bar in both windows against the equal-weight scored names",
}
COLS = {"cfo_assets_quintile": "cfo", "droa_quintile": "droa", "lowcapex_quintile": "lowcapex", "fcf_assets_quintile": "fcf"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 26: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 26: cash-flow fundamentals, keep testing until more pass.",
                                        research_memo=MEMO, strategy="round26_tests.py")
    return {rid: ids[f"Round 26: {rid}"] for rid in HYP}


def scores(tables, ticker, date):
    """dict with cfo, droa, lowcapex, fcf, acc for the latest usable fiscal year (NaN where a part is missing)."""
    out = dict.fromkeys(("cfo", "droa", "lowcapex", "fcf", "acc"), np.nan)
    wide = tables.get(ticker)
    if wide is None:
        return out
    ok = wide[(wide["avail"] < date) & (wide.index >= date - pd.Timedelta(days=455)) & wide["assets"].notna() & (wide["assets"] > 0)]
    if ok.empty:
        return out
    end, r = ok.index[-1], ok.iloc[-1]
    a = r["assets"]
    capex = r[CAPEX] if CAPEX in wide and pd.notna(r.get(CAPEX)) else np.nan
    if pd.notna(r["cfo"]):
        out["cfo"] = r["cfo"] / a
    if pd.notna(capex):
        out["lowcapex"] = -capex / a
    if pd.notna(r["cfo"]) and pd.notna(capex):
        out["fcf"] = (r["cfo"] - capex) / a
    if pd.notna(r["ni"]) and pd.notna(r["cfo"]):
        out["acc"] = -(r["ni"] - r["cfo"]) / a
    prior = wide[(wide.index >= end - pd.Timedelta(days=395)) & (wide.index <= end - pd.Timedelta(days=335)) & wide["assets"].notna() & (wide["assets"] > 0)]
    if len(prior) and pd.notna(r["ni"]) and pd.notna(prior["ni"].iloc[-1]):
        out["droa"] = r["ni"] / a - prior["ni"].iloc[-1] / prior["assets"].iloc[-1]
    return out


def active_series(rows, close_ff):
    """Gross active return per holding period of an equal-weight pick set against its benchmark names."""
    vals = {}
    for (date, weights, _, bench), nxt in zip(rows, [r[0] for r in rows[1:]]):
        if not weights:
            continue
        growth = close_ff.loc[nxt] / close_ff.loc[date] - 1
        vals[date] = float(growth[list(weights)].mean() - growth[bench].mean())
    return pd.Series(vals)


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
    tables = annual_tables(pd.concat([load_facts(), round26_data.load_facts()], ignore_index=True))
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = list(COLS.values()) + ["acc"]
    rows = {k: [] for k in names + [k + "_low" for k in COLS.values()]}
    cover = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        table = pd.DataFrame({t: scores(tables, t, date) for t in priced}).T
        k = lambda n: max(1, int(round(0.2 * n)))
        for key in names:
            s = table[key].dropna()
            ok = len(s) >= MIN_SCORED
            rows[key].append((date, equal(top(s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
            if key + "_low" in rows:
                rows[key + "_low"].append((date, equal(top(-s, k(len(s)))) if ok else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), **{key: int(table[key].notna().sum()) for key in names}})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out, corr = {}, {}
    acc_active = active_series(rows["acc"], close_ff)
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        if name in COLS.values():
            corr[name] = float(active_series(r, close_ff).corr(acc_active))
        print(f"{name:12s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                      for w, c in out[name].items() if w in JUDGED), flush=True)
    print("corr of active return with low accruals:", {k: round(v, 2) for k, v in corr.items()})
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
        add_evidence(conn, ids[rid], "backtest", f"round26_tests {rid}: {'passes' if not fails else 'fails'}. {body}; corr with low accruals {corr[COLS[rid]]:.2f}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_accruals": corr, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
