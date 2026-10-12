"""Hypothesis 24: canary-protected momentum (DAA-style), canaries read breadth, BIL takes the cash.

Score = 12 r21 + 4 r63 + 2 r126 + 1 r252 (simple close-to-close returns over trading-day lookbacks)
at each month-end close with at least 253 closes. A canary is bad when its score is <= 0. With b
bad canaries the cash fraction is CF = min(1, b / 2) and goes to BIL; the `top` highest-scoring
risky assets (regardless of sign) share the remaining 1 - CF equally. Before 253 closes: 100% BIL
at month-ends. Canaries that are not risky assets are signal-only (not held, not benchmarked).
B = 2 (each bad canary adds 50% cash) is the memo's own deviation from the published design.
See research/r3-cross-asset-momentum-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

from core.portfolio import month_ends

VERSION = 1
PARAMS = {"weights": {21: 12, 63: 4, 126: 2, 252: 1}, "cash": "BIL", "max_bad": 2}
UNIVERSES = {
    "core": {"risky": ["SPY", "IWM", "QQQ", "EFA", "EEM", "VNQ", "DBC", "GLD", "TLT", "HYG", "LQD"],
             "canaries": ["EEM", "AGG"], "top": 6, "signal_only": ("AGG",)},
    "alternate": {"risky": ["XLE", "XLK", "XLV", "XLF", "XLU", "XLP", "XLY", "XLI", "XLB"],
                  "canaries": ["EFA", "IEF"], "top": 4, "signal_only": ("EFA", "IEF")},
}


def generate_weights(bars, risky=tuple(UNIVERSES["core"]["risky"]),
                     canaries=tuple(UNIVERSES["core"]["canaries"]), top=UNIVERSES["core"]["top"],
                     cash=PARAMS["cash"], lookback_weights=PARAMS["weights"], max_bad=PARAMS["max_bad"]):
    close = pd.DataFrame({s: b["close"] for s, b in bars.items()})
    score = sum(w * (close / close.shift(k) - 1) for k, w in lookback_weights.items())
    warmup = max(lookback_weights)
    out = pd.DataFrame(np.nan, close.index, close.columns)
    for i in np.flatnonzero(month_ends(close.index)):
        row = pd.Series(0.0, index=close.columns)
        if i < warmup:
            row[cash] = 1.0
        else:
            s = score.iloc[i]
            cash_fraction = min(1.0, sum(s[c] <= 0 for c in canaries) / max_bad)
            for symbol in sorted(risky, key=lambda x: -s[x])[:top]:
                row[symbol] = (1.0 - cash_fraction) / top
            row[cash] += cash_fraction
        out.iloc[i] = row.to_numpy()
    return out
