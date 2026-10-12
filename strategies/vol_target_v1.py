"""Hypothesis 2: hold at weight min(1, 15% / annualized 20-day realized volatility).

See research/trend-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np

VERSION = 1
PARAMS = {"target_vol": 0.15, "lookback": 20}


def generate_signals(bars, target_vol=PARAMS["target_vol"], lookback=PARAMS["lookback"]):
    vol = bars["close"].pct_change().rolling(lookback).std() * np.sqrt(252)
    return (target_vol / vol).clip(upper=1.0).fillna(0.0)
