"""Discovery universe and the first pre-registered growth strategy, G1 (trend-filtered momentum rotation).

Pure functions of price history; no I/O, no orders. Everything here is research output: the strategy is a Q-tier
hypothesis, not a validated edge, and every idea derived from it must carry that label.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .domain.models import Bar

# Research mandate (spec 2): liquid US ETFs across sectors/themes/asset classes plus the largest growth names.
# Survivorship caveat: names were chosen from today's leaders, so results are biased upward (disclosed in G1).
UNIVERSE = [
    "SPY", "QQQ", "VTI", "VXUS", "IWM", "RSP", "XLK", "XLV", "XLE", "XLF", "XLI", "XLU", "XLP", "XLY", "XLC", "XLB",
    "XLRE", "SMH", "IBB", "ITA", "GLD", "SLV", "TLT",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "LLY", "TSM", "NFLX", "COST", "V",
]
G1_ID = "G1_trend_momentum_rotation"
LOOKBACK, SKIP, TREND, TOP_N = 126, 5, 200, 5
CASH_BUFFER_WEIGHT = 0.99      # 1% always held back for costs, so the strategy can never imply leverage


def iid(symbol: str) -> str:
    return f"EQ:US:{symbol}"


@dataclass(frozen=True)
class Params:
    lookback: int = LOOKBACK
    skip: int = SKIP
    trend: int = TREND
    top_n: int = TOP_N


DEFAULT = Params()


def momentum(bars: list[Bar], p: Params = DEFAULT) -> float | None:
    """~6-month total return skipping the most recent week; None without enough history."""
    if len(bars) < max(p.lookback + p.skip + 1, p.trend):
        return None
    return bars[-1 - p.skip].close / bars[-1 - p.skip - p.lookback].close - 1


def trend_ok(bars: list[Bar], p: Params = DEFAULT) -> bool:
    if len(bars) < p.trend:
        return False
    return bars[-1].close > sum(b.close for b in bars[-p.trend:]) / p.trend


def rank(hist: dict[str, list[Bar]], p: Params = DEFAULT) -> list[tuple[str, float]]:
    """Eligible instruments (positive momentum AND above the 200-day average), best first. Ties broken by id."""
    out = []
    for i, bs in hist.items():
        m = momentum(bs, p)
        if m is not None and m > 0 and trend_ok(bs, p):
            out.append((i, m))
    return sorted(out, key=lambda t: (-t[1], t[0]))


def is_rebalance_day(hist_dates: list[str], d: str) -> bool:
    """First session of a calendar month (the decision is taken at that day's close)."""
    k = hist_dates.index(d)
    return k == 0 or hist_dates[k - 1][:7] != d[:7]


def target_weights(hist: dict[str, list[Bar]], top_n: int | None = None, p: Params = DEFAULT) -> dict[str, float]:
    top_n = top_n or p.top_n
    ranked = rank(hist, p)[:top_n]
    return {i: CASH_BUFFER_WEIGHT / top_n for i, _ in ranked}   # unfilled slots stay in cash (trend filter -> defensive)


def g1_strategy(hist: dict[str, list[Bar]], p: Params = DEFAULT) -> dict[str, float]:
    """Stateless: holds the weights chosen at the latest rebalance day on or before today (data up to that day only)."""
    dates = sorted({b.session_date for bs in hist.values() for b in bs})
    if not dates:
        return {}
    last_reb = next((d for d in reversed(dates) if is_rebalance_day(dates, d)), None)
    if last_reb is None:
        return {}
    cut = {i: [b for b in bs if b.session_date <= last_reb] for i, bs in hist.items()}
    return target_weights(cut, None, p)


def with_params(p: Params):
    return lambda hist: g1_strategy(hist, p)


def buy_and_hold(instrument_id: str):
    return lambda hist: {instrument_id: 1.0}


@dataclass(frozen=True)
class Idea:
    instrument_id: str
    momentum: float
    suggested_weight: float
    rationale: str


def current_ideas(hist: dict[str, list[Bar]], held: set[str], max_weight_each: float = 0.03) -> list[Idea]:
    """Top-ranked eligible names the owner does not already hold, sized small (capped), for advisory use only."""
    out = []
    for i, m in rank(hist)[:TOP_N * 2]:
        if i.rsplit(":", 1)[-1] in held or i in held:
            continue
        out.append(Idea(i, m, max_weight_each,
                        f"{i.rsplit(':', 1)[-1]}: ~6-month momentum {m:+.0%} (skipping last week) and above its 200-day average. "
                        "Basis: strategy G1, backtested only - not independently validated."))
    return out[:3]
