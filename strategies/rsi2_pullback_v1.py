"""Hypothesis 5: buy when RSI(2) < 10 above the 200-day SMA; sell at the first close above the 5-day SMA.

See research/mean-reversion-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

VERSION = 1
PARAMS = {"rsi_period": 2, "entry_rsi": 10, "trend": 200, "exit_sma": 5}


def wilder_rsi(close, period):
    change = close.diff()
    gain = change.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-change.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def generate_signals(bars, rsi_period=PARAMS["rsi_period"], entry_rsi=PARAMS["entry_rsi"],
                     trend=PARAMS["trend"], exit_sma=PARAMS["exit_sma"]):
    close = bars["close"]
    entry = (wilder_rsi(close, rsi_period) < entry_rsi) & (close > close.rolling(trend).mean())
    exit_ = close > close.rolling(exit_sma).mean()
    weights, held = [], False
    for enter, leave in zip(entry, exit_):
        if held and leave:
            held = False
        elif not held and enter:
            held = True
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
