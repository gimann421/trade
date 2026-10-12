"""Hypothesis 10: flat for 10 trading days after a down day whose true range exceeds 2x the
prior 20-day average true range; each new shock restarts the count.

See research/volatility-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

VERSION = 1
PARAMS = {"atr": 20, "mult": 2.0, "timeout": 10}


def generate_signals(bars, atr=PARAMS["atr"], mult=PARAMS["mult"], timeout=PARAMS["timeout"]):
    close, prev = bars["close"], bars["close"].shift(1)
    true_range = pd.concat([bars["high"], prev], axis=1).max(axis=1) - \
        pd.concat([bars["low"], prev], axis=1).min(axis=1)
    shock = (close < prev) & (true_range > mult * true_range.rolling(atr).mean().shift(1))
    # Weight 0 on the shock day and the 9 after it = flat over the next 10 days' returns.
    return 1.0 - shock.astype(float).rolling(timeout, min_periods=1).max()
