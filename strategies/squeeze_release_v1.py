"""Hypothesis 21: squeeze-release long (upside breakout after range compression).

ATR%10 = 10-day mean true range / close. Compressed = ATR%10 <= its trailing-250-day 20th
percentile (including today). Long at a close above the highest close of the prior 10 days when
a compressed close occurred in the last 5 closes; exit at the first close below the lowest close
of the prior 10 days or after 40 trading days (the exit bar stays flat). Flat for the first 260
bars. See research/r2-volatility-regime-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

VERSION = 1
PARAMS = {"atr": 10, "pct_window": 250, "pct": 0.20, "recent": 5, "channel": 10,
          "max_hold": 40, "warmup": 260}


def generate_signals(bars, atr=PARAMS["atr"], pct_window=PARAMS["pct_window"], pct=PARAMS["pct"],
                     recent=PARAMS["recent"], channel=PARAMS["channel"],
                     max_hold=PARAMS["max_hold"], warmup=PARAMS["warmup"]):
    close, prev = bars["close"], bars["close"].shift(1)
    true_range = pd.concat([bars["high"], prev], axis=1).max(axis=1) - \
        pd.concat([bars["low"], prev], axis=1).min(axis=1)
    atr_pct = true_range.rolling(atr).mean() / close
    compressed = (atr_pct <= atr_pct.rolling(pct_window).quantile(pct)).astype(float)
    squeezed = (compressed.rolling(recent).max() == 1).to_numpy()
    breakout = (close > close.rolling(channel).max().shift(1)).to_numpy()
    breakdown = (close < close.rolling(channel).min().shift(1)).to_numpy()
    weights, held, days = [], False, 0
    for i in range(len(close)):
        if i < warmup:
            weights.append(0.0)
            continue
        if held:
            days += 1
            if breakdown[i] or days >= max_hold:
                held = False
        elif squeezed[i] and breakout[i]:
            held, days = True, 0
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
