"""Round 28 follow-up on rnd_quintile, the one rule that cleared the bar (research/r28-leverage-rnd-stability-2026-10-22.md, "Robustness").
Written after the pass was seen: neighbours and diagnostics, not new hypotheses.

    PYTHONPATH=. python research/round28_robust.py
"""

import json

import numpy as np
import pandas as pd

from core.config import ROOT
from core.industry import load_sic
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research import round28_data
from research.round18_tests import equal, run_rule, top
from research.round23_tests import targets_from
from research.round25_data import load_facts
from research.round26_tests import active_series
from research.round28_tests import MIN_SCORED, scores, tables_from
from research.round6_scan import load_inputs, load_module


def main():
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    close_ff = stocks.ffill()
    tables = tables_from(pd.concat([load_facts(), round28_data.load_facts()], ignore_index=True))
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = ["quintile", "decile", "tercile", "ex_techhealth", "within_industry", "vs_all_priced", "mirror_low_rnd"]
    rows = {k: [] for k in names}
    sizes = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        rnd = pd.Series({t: scores(tables, t, date)["rnd"] for t in priced}).dropna()
        k = lambda s, f: max(1, int(round(f * len(s))))
        ok = len(rnd) >= MIN_SCORED
        rows["quintile"].append((date, equal(top(rnd, k(rnd, 0.2))) if ok else {}, list(rnd.index), list(rnd.index)))
        rows["decile"].append((date, equal(top(rnd, k(rnd, 0.1))) if ok else {}, list(rnd.index), list(rnd.index)))
        rows["tercile"].append((date, equal(top(rnd, k(rnd, 1 / 3))) if ok else {}, list(rnd.index), list(rnd.index)))
        ex = rnd[[t for t in rnd.index if t not in techhealth]]
        oke = len(ex) >= MIN_SCORED
        rows["ex_techhealth"].append((date, equal(top(ex, k(ex, 0.2))) if oke else {}, list(ex.index), list(ex.index)))
        grp = sic.reindex(rnd.index)
        pct = rnd.groupby(grp).rank(pct=True)
        size = grp.map(grp.value_counts())
        w = rnd[(pct >= 0.8) & (size >= 4)]
        rows["within_industry"].append((date, equal(list(w.index)) if ok and len(w) else {}, list(rnd.index), list(rnd.index)))
        rows["vs_all_priced"].append((date, equal(top(rnd, k(rnd, 0.2))) if ok else {}, list(rnd.index), priced))
        rows["mirror_low_rnd"].append((date, equal(top(-rnd, k(rnd, 0.2))) if ok else {}, list(rnd.index), list(rnd.index)))
        sizes.append({"date": str(date.date()), "scored": len(rnd), "tech_health_share_of_picks": float(np.mean([t in techhealth for t in top(rnd, k(rnd, 0.2))])) if ok else None})
    out = {}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:16s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%}"
                                       for w, c in out[name].items()), flush=True)
    print("tech/health share of quintile picks (first, mid, last):", [sizes[i]["tech_health_share_of_picks"] for i in (0, len(sizes) // 2, -1)])
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
    (ROOT / "backtests" / "round28_tests").mkdir(parents=True, exist_ok=True)
    (ROOT / "backtests" / "round28_tests" / "robustness.json").write_text(json.dumps({"variants": out, "yearly_active": {int(y): v for y, v in yearly.items()}, "composition": sizes}, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
