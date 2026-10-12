"""Hypothesis 25: breadth-protected allocation (PAA-style), the universe's own breadth sets the cash.

MOM = close / mean(last 252 closes) - 1 at each month-end close with at least 252 closes. With
n of the N risky assets above their SMA (MOM > 0), the cash fraction is BF = min(1, (N - n) / (N / 2))
and goes to BIL; the floor(N / 2) highest-MOM assets (regardless of sign) share 1 - BF equally.
Before 252 closes: 100% BIL at month-ends.
See research/r3-cross-asset-momentum-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

from core.portfolio import month_ends

VERSION = 1
PARAMS = {"window": 252, "cash": "BIL"}
UNIVERSES = {
    "core": {"risky": ["SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "DBC", "GLD", "HYG", "LQD", "TLT", "IEF"],
             "signal_only": ()},
    "alternate": {"risky": ["XLE", "XLK", "XLV", "XLF", "XLU", "XLP", "XLY", "XLI", "XLB"],
                  "signal_only": ()},
}


def generate_weights(bars, risky=tuple(UNIVERSES["core"]["risky"]), cash=PARAMS["cash"],
                     window=PARAMS["window"]):
    close = pd.DataFrame({s: b["close"] for s, b in bars.items()})
    momentum = close / close.rolling(window).mean() - 1
    n_assets, keep = len(risky), len(risky) // 2
    out = pd.DataFrame(np.nan, close.index, close.columns)
    for i in np.flatnonzero(month_ends(close.index)):
        row = pd.Series(0.0, index=close.columns)
        if i + 1 < window:
            row[cash] = 1.0
        else:
            m = momentum.iloc[i]
            n_up = sum(m[s] > 0 for s in risky)
            cash_fraction = min(1.0, (n_assets - n_up) / (n_assets / 2))
            for symbol in sorted(risky, key=lambda x: -m[x])[:keep]:
                row[symbol] = (1.0 - cash_fraction) / keep
            row[cash] += cash_fraction
        out.iloc[i] = row.to_numpy()
    return out
