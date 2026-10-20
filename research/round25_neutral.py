"""Round 25 follow-up diagnostics for lowaccruals_quintile (report only, written after the pass was seen):
excluding oil and gas, and ranking within two-digit SIC groups.

    PYTHONPATH=. python research/round25_neutral.py
"""

import pandas as pd

from core.industry import load_sic
from core.portfolio import month_ends
from core.universe import members_on
from research.round18_tests import equal, run_rule, top
from research.round25_tests import MIN_SCORED, annual_tables, scores_at
from research.round6_scan import load_inputs, load_module


def main():
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    close_ff = stocks.ffill()
    tables, sic = annual_tables(), load_sic()
    energy = set(sic.index[sic.isin(["13", "29"])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    rows = {"ex_oil_gas": [], "within_industry": []}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        acc = pd.Series({t: scores_at(tables, t, date)[1] for t in priced}).dropna()
        ex = acc[[t for t in acc.index if t not in energy]]
        rows["ex_oil_gas"].append((date, equal(top(ex, max(1, int(round(0.2 * len(ex)))))) if len(ex) >= MIN_SCORED else {}, list(ex.index), list(ex.index)))
        g = sic.reindex(acc.index)
        size = g.map(g.value_counts())
        keep = acc[(size >= 4).reindex(acc.index).fillna(False)]
        z = keep.groupby(sic[keep.index]).transform(lambda x: (x - x.mean()) / (x.std(ddof=0) or 1.0))
        rows["within_industry"].append((date, equal(top(z, max(1, int(round(0.2 * len(z)))))) if len(z) >= MIN_SCORED else {}, list(z.index), list(z.index)))
    for k, r in rows.items():
        out = run_rule(r, close_ff, index)
        print(f"{k:16s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%}" for w, c in out.items()))


if __name__ == "__main__":
    main()
