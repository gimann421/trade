"""Round 22 side check (report only): the band reversal rule on the three possible 3-session decision phases.

    PYTHONPATH=. python research/round22_phase.py
"""

import numpy as np
import pandas as pd

from core.data import load_bars
from core.intraday import sample_tickers
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round5_verdicts import window_stats
from research.round6_scan import load_inputs, load_module
from research.round8_short_horizon import WINDOWS, cleaned, dirty_index


def main():
    fs, rm, sh = load_module("factor_scan_v1"), load_module("residual_momentum_v1"), load_module("short_horizon_v5")
    fs.FIRST_DECISION = sh.FIRST_DECISION
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    dirty = dirty_index(index)
    full = stocks.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    score = -(stocks / stocks.shift(5) - 1)
    score[sh.CASH] = np.nan
    score = score.reindex(columns=full.columns)
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    _, bench_targets, bdetail = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, full.columns), index[month_ends(index)], membership, None)
    first_hold = index[index.get_loc(bdetail[0]["date"]) + 1]
    bench = {b: cleaned(simulate(close_ff, bench_targets, b), dirty) for b in (5.0, 10.0)}
    start = index.searchsorted(pd.Timestamp(sh.FIRST_DECISION))
    for phase in range(3):
        decisions = list(index[start + phase::3])
        targets, _ = sh.generate_targets(sh.PARENT_RULE, full, score, decisions, lambda d: members_on(membership, d))
        for b in (5.0, 10.0):
            run = cleaned(simulate(close_ff, targets, b), dirty)
            print(f"phase {phase} first decision {decisions[0].date()} {b:.0f} bps:", "  ".join(
                f"{w} {window_stats(run, bench[b], first_hold, *rng)[2]['net_active']:+6.1%}" for w, rng in WINDOWS.items()), flush=True)


if __name__ == "__main__":
    main()
