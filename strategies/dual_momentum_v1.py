"""Hypothesis 23: dual momentum, top 2 of a six-asset risky set with a BIL absolute filter.

At each month-end close with at least 253 closes: score = close_t / close_{t-252} - 1 for every
risky asset and for BIL. The two highest-scoring risky assets (ties by listed order) get 0.5
each; a half whose score does not beat BIL's goes to BIL instead. Before 253 closes: 100% BIL
at month-ends. Weights are emitted on month-end rows only (all-NaN elsewhere = no trade).
See research/r3-cross-asset-momentum-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

from core.portfolio import month_ends

VERSION = 1
PARAMS = {"lookback": 252, "top": 2, "cash": "BIL"}
UNIVERSES = {
    "core": {"risky": ["SPY", "EFA", "EEM", "VNQ", "TLT", "GLD"], "signal_only": ()},
    "alternate": {"risky": ["QQQ", "IWM", "LQD", "HYG", "IEF", "DBC"], "signal_only": ()},
}


def generate_weights(bars, risky=tuple(UNIVERSES["core"]["risky"]), cash=PARAMS["cash"],
                     lookback=PARAMS["lookback"], top=PARAMS["top"]):
    close = pd.DataFrame({s: b["close"] for s, b in bars.items()})
    score = close / close.shift(lookback) - 1
    out = pd.DataFrame(np.nan, close.index, close.columns)
    for i in np.flatnonzero(month_ends(close.index)):
        row = pd.Series(0.0, index=close.columns)
        if i < lookback:                       # fewer than lookback + 1 closes
            row[cash] = 1.0
        else:
            s = score.iloc[i]
            for symbol in sorted(risky, key=lambda x: -s[x])[:top]:
                row[symbol if s[symbol] > s[cash] else cash] += 1.0 / top
        out.iloc[i] = row.to_numpy()
    return out
