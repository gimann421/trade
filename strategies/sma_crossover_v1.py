"""Long when the fast moving average is above the slow one, flat otherwise.

Example strategy showing the file contract; not a recommendation.
"""

VERSION = 1
PARAMS = {"fast": 50, "slow": 200}


def generate_signals(bars, fast=PARAMS["fast"], slow=PARAMS["slow"]):
    close = bars["close"]
    # Comparisons against the NaN warm-up period evaluate False, so the signal starts flat.
    return (close.rolling(fast).mean() > close.rolling(slow).mean()).astype(float)
