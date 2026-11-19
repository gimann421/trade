"""Pre-written candidate strategies for the continuous search. All are authored BEFORE any is tested, each with a distinct,
published premise and fixed parameters, over the repo's long ETF history. Nothing here is tuned on results; nearby
settings (``variants``) exist only for the Red Team's parameter-neighbour test.

Every candidate is long-only, no leverage (weights sum to at most 0.99), monthly or daily rule on bars up to the decision day.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Callable

from .domain.models import Bar
from .ideas import CASH_BUFFER_WEIGHT as CB, is_rebalance_day, iid

Hist = dict[str, list[Bar]]


def _sma(bs: list[Bar], n: int) -> float | None:
    return sum(b.close for b in bs[-n:]) / n if len(bs) >= n else None


def _ret(bs: list[Bar], n: int) -> float | None:
    return bs[-1].close / bs[-1 - n].close - 1 if len(bs) > n else None


def _vol(bs: list[Bar], n: int) -> float | None:
    if len(bs) <= n:
        return None
    r = [bs[k].close / bs[k - 1].close - 1 for k in range(len(bs) - n, len(bs))]
    m = sum(r) / n
    return (sum((x - m) ** 2 for x in r) / (n - 1)) ** 0.5


def monthly(rule: Callable[[Hist], dict[str, float]]) -> Callable[[Hist], dict[str, float]]:
    """Hold the weights chosen at the latest first-session-of-month close, using only data up to that day."""
    def strat(hist: Hist) -> dict[str, float]:
        dates = sorted({b.session_date for bs in hist.values() for b in bs})
        if not dates:
            return {}
        d = next((x for x in reversed(dates) if is_rebalance_day(dates, x)), None)
        if d is None:
            return {}
        return rule({i: [b for b in bs if b.session_date <= d] for i, bs in hist.items()})
    return strat


# ---- rules -----------------------------------------------------------------------------------------------------------
def dual_momentum(h: Hist, lookback: int = 252) -> dict[str, float]:
    s, e, b, a = (h.get(iid(x)) for x in ("SPY", "EFA", "SHY", "AGG"))
    if not (s and e and b and a):
        return {}
    rs, re_, rb = _ret(s, lookback), _ret(e, lookback), _ret(b, lookback)
    if None in (rs, re_, rb):
        return {}
    best = iid("SPY") if rs >= re_ else iid("EFA")
    return {best: CB} if max(rs, re_) > rb else {iid("AGG"): CB}


def faber_gtaa(h: Hist, sma: int = 200) -> dict[str, float]:
    assets = [iid(x) for x in ("SPY", "EFA", "IEF", "VNQ", "GLD")]
    on = [i for i in assets if i in h and (m := _sma(h[i], sma)) is not None and h[i][-1].close > m]
    return {i: CB / len(assets) for i in on}


def sector_rotation(h: Hist, lookback: int = 126, top: int = 3) -> dict[str, float]:
    sec = [iid(x) for x in "XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()]
    sc = sorted(((_ret(h[i], lookback), i) for i in sec if i in h and _ret(h[i], lookback) is not None), reverse=True)[:top]
    return {i: CB / top for _, i in sc}


def inverse_vol(h: Hist, window: int = 63) -> dict[str, float]:
    assets = [iid(x) for x in "SPY EFA TLT IEF GLD VNQ LQD".split()]
    v = {i: _vol(h[i], window) for i in assets if i in h}
    v = {i: x for i, x in v.items() if x}
    tot = sum(1 / x for x in v.values())
    return {i: CB * (1 / x) / tot for i, x in v.items()} if v else {}


def spy_trend(h: Hist, sma: int = 200) -> dict[str, float]:
    s, b = h.get(iid("SPY")), h.get(iid("SHY"))
    if not s or not b or _sma(s, sma) is None:
        return {}
    return {iid("SPY"): CB} if s[-1].close > _sma(s, sma) else {iid("SHY"): CB}


def vol_target(h: Hist, target: float = 0.10, window: int = 20) -> dict[str, float]:
    s = h.get(iid("SPY"))
    v = _vol(s, window) if s else None
    if not v:
        return {}
    return {iid("SPY"): min(CB, target / (v * 252 ** 0.5))}


def stock_bond_rotation(h: Hist, lookback: int = 63) -> dict[str, float]:
    s, t = h.get(iid("SPY")), h.get(iid("TLT"))
    if not s or not t:
        return {}
    rs, rt = _ret(s, lookback), _ret(t, lookback)
    if rs is None or rt is None or max(rs, rt) <= 0:
        return {}
    return {iid("SPY") if rs >= rt else iid("TLT"): CB}


def multi_asset_momentum(h: Hist, lookback: int = 126, top: int = 3) -> dict[str, float]:
    assets = [iid(x) for x in "SPY EFA EEM TLT IEF LQD GLD VNQ".split()]
    sc = sorted(((_ret(h[i], lookback), i) for i in assets if i in h and _ret(h[i], lookback) is not None), reverse=True)[:top]
    return {i: CB / top for r, i in sc if r > 0}


def equal_weight_assets(h: Hist) -> dict[str, float]:
    assets = [iid(x) for x in "SPY EFA EEM TLT IEF LQD GLD VNQ".split() if iid(x) in h]
    return {i: CB / 8 for i in assets}


def turn_of_month(hist: Hist, first: int = 3, last: int = 27) -> dict[str, float]:
    """Daily rule (not monthly): hold SPY around the turn of the month by calendar day, otherwise cash."""
    s = hist.get(iid("SPY"))
    if not s:
        return {}
    day = int(s[-1].session_date[8:10])
    return {iid("SPY"): CB} if day >= last or day <= first - 1 else {}


@dataclass(frozen=True)
class Candidate:
    cid: str
    title: str
    rationale: str
    signal: str
    symbols: tuple[str, ...]
    strategy: Callable
    variants: tuple = field(default_factory=tuple)


def _c(cid, title, rationale, signal, symbols, rule, variants, is_monthly=True):
    wrap = monthly if is_monthly else (lambda f: f)
    return Candidate(cid, title, rationale, signal, tuple(symbols.split()), wrap(rule), tuple(wrap(v) for v in variants))


CANDIDATES: list[Candidate] = [
    _c("N01_dual_momentum", "Dual momentum: US vs international vs bonds",
       "Antonacci's dual momentum: relative strength picks the stronger equity market, absolute momentum moves to bonds when equities do not beat cash.",
       "Monthly: if the better of SPY and EFA 12-month return beats SHY's, hold it; otherwise hold AGG.", "SPY EFA SHY AGG",
       dual_momentum, [partial(dual_momentum, lookback=189), partial(dual_momentum, lookback=315)]),
    _c("N02_faber_gtaa", "Faber trend-following across five asset classes",
       "Faber (2007): a 10-month moving-average timing rule on a diversified set of asset classes cuts drawdowns while keeping most of the return.",
       "Monthly: hold each of SPY, EFA, IEF, VNQ, GLD (1/5 each) only while above its 200-session average, else cash.", "SPY EFA IEF VNQ GLD",
       faber_gtaa, [partial(faber_gtaa, sma=150), partial(faber_gtaa, sma=250)]),
    _c("N03_sector_rotation", "Sector relative-strength rotation",
       "Sector momentum (Moskowitz and Grinblatt): industries that did best over the past months tend to keep outperforming over the next few.",
       "Monthly: hold the 3 of 9 sector ETFs with the best 126-session return, equal weight.", "XLB XLE XLF XLI XLK XLP XLU XLV XLY",
       sector_rotation, [partial(sector_rotation, lookback=63), partial(sector_rotation, lookback=189), partial(sector_rotation, top=2), partial(sector_rotation, top=4)]),
    _c("N04_inverse_vol", "Inverse-volatility multi-asset (risk parity lite)",
       "Risk-balanced portfolios (Qian; Asness et al.): weighting by inverse volatility lets bonds and gold carry more weight and smooths the ride without forecasting returns.",
       "Monthly: weight SPY, EFA, TLT, IEF, GLD, VNQ, LQD by 1/volatility (63 sessions), sum 99%.", "SPY EFA TLT IEF GLD VNQ LQD",
       inverse_vol, [partial(inverse_vol, window=42), partial(inverse_vol, window=126)]),
    _c("N05_spy_trend", "S&P 500 trend filter with short-bond fallback",
       "A long-only trend filter on the broad market avoids most large bear markets (Faber; Hurst, Ooi, Pedersen).",
       "Monthly: hold SPY while it is above its 200-session average, otherwise SHY.", "SPY SHY",
       spy_trend, [partial(spy_trend, sma=150), partial(spy_trend, sma=250)]),
    _c("N06_vol_target", "Volatility-targeted S&P 500",
       "Volatility managing (Moreira and Muir): scaling exposure down when recent volatility is high improves risk-adjusted returns because volatility clusters.",
       "Daily rule at each close: SPY weight = min(99%, 10% / annualised 20-session volatility), rest cash.", "SPY",
       vol_target, [partial(vol_target, target=0.08), partial(vol_target, target=0.12), partial(vol_target, window=42)], is_monthly=False),
    _c("N07_stock_bond_rotation", "Stocks versus long bonds rotation",
       "Cross-asset momentum: the asset class with the stronger recent trend tends to keep leading over the next months (Asness, Moskowitz, Pedersen).",
       "Monthly: hold SPY or TLT, whichever has the higher 63-session return, only if that return is positive; else cash.", "SPY TLT",
       stock_bond_rotation, [partial(stock_bond_rotation, lookback=42), partial(stock_bond_rotation, lookback=126)]),
    _c("N08_multi_asset_momentum", "Multi-asset class momentum",
       "Time-series and cross-sectional momentum exist in every major asset class (Asness, Moskowitz, Pedersen 2013).",
       "Monthly: of SPY, EFA, EEM, TLT, IEF, LQD, GLD, VNQ hold the 3 with the best positive 126-session return.", "SPY EFA EEM TLT IEF LQD GLD VNQ",
       multi_asset_momentum, [partial(multi_asset_momentum, lookback=63), partial(multi_asset_momentum, lookback=189), partial(multi_asset_momentum, top=2), partial(multi_asset_momentum, top=4)]),
    _c("N09_equal_weight_assets", "Equal-weight diversified asset classes (no-skill baseline)",
       "A 1/N diversified portfolio is a hard-to-beat benchmark (DeMiguel, Garlappi, Uppal); included to show what no skill delivers.",
       "Monthly: hold SPY, EFA, EEM, TLT, IEF, LQD, GLD, VNQ at equal weight.", "SPY EFA EEM TLT IEF LQD GLD VNQ",
       equal_weight_assets, [partial(equal_weight_assets)]),
    _c("N10_turn_of_month", "Turn-of-the-month effect in the S&P 500",
       "Equity returns concentrate around the turn of the month (Lakonishok and Smidt; McConnell and Xu) as flows arrive; capital sits in cash otherwise.",
       "Daily: hold SPY from the 27th through the 2nd calendar day of each month, otherwise cash.", "SPY",
       turn_of_month, [partial(turn_of_month, first=4), partial(turn_of_month, last=26)], is_monthly=False),
]
