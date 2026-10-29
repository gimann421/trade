"""Round 30 follow-up on cash_quintile, the one rule that cleared the bar (research/r30-cash-profit-tax-2026-10-29.md, "Robustness").
Written after the pass was seen: neighbours and diagnostics, not new hypotheses.

    PYTHONPATH=. python research/round30_robust.py
"""

import json

import numpy as np
import pandas as pd

from core.config import ROOT
from core.industry import load_sic
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research import round28_data, round30_data
from research.round18_tests import equal, run_rule, top
from research.round23_tests import targets_from
from research.round25_data import load_facts
from research.round28_tests import MIN_SCORED, scores as rnd_scores, tables_from
from research.round30_tests import extra_tables, scores
from research.round6_scan import load_inputs, load_module


def main():
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    close_ff = stocks.ffill()
    tables = tables_from(pd.concat([load_facts(), round28_data.load_facts()], ignore_index=True))
    extra = extra_tables(round30_data.load_facts())
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = ["quintile", "decile", "tercile", "ex_techhealth", "within_industry", "no_rnd_names", "vs_all_priced"]
    rows = {k: [] for k in names}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        cash = pd.Series({t: scores(tables, extra, t, date)["cash"] for t in priced}).dropna()
        k = lambda s, f: max(1, int(round(f * len(s))))
        ok = len(cash) >= MIN_SCORED
        rows["quintile"].append((date, equal(top(cash, k(cash, 0.2))) if ok else {}, list(cash.index), list(cash.index)))
        rows["decile"].append((date, equal(top(cash, k(cash, 0.1))) if ok else {}, list(cash.index), list(cash.index)))
        rows["tercile"].append((date, equal(top(cash, k(cash, 1 / 3))) if ok else {}, list(cash.index), list(cash.index)))
        ex = cash[[t for t in cash.index if t not in techhealth]]
        oke = len(ex) >= MIN_SCORED
        rows["ex_techhealth"].append((date, equal(top(ex, k(ex, 0.2))) if oke else {}, list(ex.index), list(ex.index)))
        grp = sic.reindex(cash.index)
        pct = cash.groupby(grp).rank(pct=True)
        size = grp.map(grp.value_counts())
        w = cash[(pct >= 0.8) & (size >= 4)]
        rows["within_industry"].append((date, equal(list(w.index)) if ok and len(w) else {}, list(cash.index), list(cash.index)))
        rnd_names = {t for t in cash.index if pd.notna(rnd_scores(tables, t, date)["rnd"])}
        nr = cash[[t for t in cash.index if t not in rnd_names]]
        okn = len(nr) >= MIN_SCORED
        rows["no_rnd_names"].append((date, equal(top(nr, k(nr, 0.2))) if okn else {}, list(nr.index), list(nr.index)))
        rows["vs_all_priced"].append((date, equal(top(cash, k(cash, 0.2))) if ok else {}, list(cash.index), priced))
    out = {}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:16s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%}"
                                       for w, c in out[name].items() if w in ("IS", "OOS")), flush=True)
    r = rows["quintile"]
    strat = simulate(close_ff, targets_from(r, close_ff, index), 5.0)["returns"]
    bench_t = pd.DataFrame(np.nan, index, close_ff.columns)
    for d, w, rk, p in r:
        bench_t.loc[d] = 0.0
        bench_t.loc[d, rk] = 1.0 / len(rk)
    bench = simulate(close_ff, bench_t, 5.0)["returns"]
    active = (strat - bench).loc[index[index.get_loc(r[0][0]) + 1]:]
    yearly = active.groupby(active.index.year).apply(lambda x: float((1 + x).prod() - 1))
    print("active return by calendar year:", {int(y): round(v, 4) for y, v in yearly.items()})
    print("share of years positive:", float((yearly > 0).mean()))
    (ROOT / "backtests" / "round30_tests").mkdir(parents=True, exist_ok=True)
    (ROOT / "backtests" / "round30_tests" / "robustness.json").write_text(json.dumps({"variants": out, "yearly_active": {int(y): v for y, v in yearly.items()}}, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
