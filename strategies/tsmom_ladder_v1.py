"""Hypothesis 3: weight = share of the 21/63/126/252-day trailing returns that are positive.

See research/trend-analyst-2026-10-12.md. Not a recommendation.
"""

VERSION = 1
PARAMS = {"lookbacks": (21, 63, 126, 252)}


def generate_signals(bars, lookbacks=PARAMS["lookbacks"]):
    close = bars["close"]
    # Before a lookback has enough history its comparison is False, so that leg counts as 0.
    legs = [(close / close.shift(n) > 1).astype(float) for n in lookbacks]
    return sum(legs) / len(legs)
