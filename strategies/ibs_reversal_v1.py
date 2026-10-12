"""Hypothesis 7: hold for one day after a close in the bottom 20% of the day's range, above the 200-day SMA.

See research/mean-reversion-analyst-2026-10-12.md. Not a recommendation.
"""

VERSION = 1
PARAMS = {"ibs_max": 0.2, "trend": 200}


def generate_signals(bars, ibs_max=PARAMS["ibs_max"], trend=PARAMS["trend"]):
    close, high, low = bars["close"], bars["high"], bars["low"]
    span = (high - low).where(high > low)  # no range, no signal
    ibs = (close - low) / span
    return ((ibs < ibs_max) & (close > close.rolling(trend).mean())).astype(float)
