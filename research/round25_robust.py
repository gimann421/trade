"""Round 25 follow-up on the one rule that cleared the bar, lowaccruals_quintile (research/r25-quality-2026-10-20.md, section "Robustness").
These checks were written after the pass was seen, so they are neighbours and diagnostics, not new hypotheses.

    PYTHONPATH=. python research/round25_robust.py
"""

import json

import numpy as np
import pandas as pd

from core.config import ROOT
from core.industry import load_sic
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round18_tests import equal, run_rule, top
from research.round23_tests import targets_from
from research.round25_tests import MIN_SCORED, annual_tables, scores_at
from research.round6_scan import load_inputs, load_module


def main():
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    close_ff = stocks.ffill()
    tables = annual_tables()
    sic = load_sic()
    fin = set(sic.index[sic.astype(int).between(60, 67)])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    variants = {"quintile": (0.2, False), "decile": (0.1, False), "tercile": (1 / 3, False), "quintile_ex_financials": (0.2, True)}
    rows = {k: [] for k in variants}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        acc = pd.Series({t: scores_at(tables, t, date)[1] for t in priced}).dropna()
        for k, (frac, exfin) in variants.items():
            s = acc[[t for t in acc.index if not (exfin and t in fin)]]
            n = max(1, int(round(frac * len(s))))
            rows[k].append((date, equal(top(s, n)) if len(s) >= MIN_SCORED else {}, list(s.index), list(s.index)))
    out = {}
    for k, r in rows.items():
        out[k] = run_rule(r, close_ff, index)
        print(f"{k:24s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%}"
                                      for w, c in out[k].items()), flush=True)
    # calendar-year active returns of the quintile rule
    r = rows["quintile"]
    strat = simulate(close_ff, targets_from([(d, w, rk, p) for d, w, rk, p in r], close_ff, index), 5.0)["returns"]
    bench_t = pd.DataFrame(np.nan, index, close_ff.columns)
    for d, w, rk, p in r:
        bench_t.loc[d] = 0.0
        names = rk if w else p
        bench_t.loc[d, names] = 1.0 / len(names)
    bench = simulate(close_ff, bench_t, 5.0)["returns"]
    first = index[index.get_loc(r[0][0]) + 1]
    active = (strat - bench).loc[first:]
    yearly = active.groupby(active.index.year).apply(lambda x: float((1 + x).prod() - 1))
    print("active return by calendar year:", {int(y): round(v, 4) for y, v in yearly.items()})
    print("share of years with positive active return:", float((yearly > 0).mean()))
    (ROOT / "backtests" / "round25_tests").mkdir(parents=True, exist_ok=True)
    (ROOT / "backtests" / "round25_tests" / "robustness.json").write_text(json.dumps({"variants": out, "yearly_active": {int(y): v for y, v in yearly.items()}}, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
