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


# ---- batch 2 rules (authored before any was tested) ---------------------------------------------------------------------
def value_growth(h: Hist, lookback: int = 126) -> dict[str, float]:
    v, g, b = h.get(iid("IWD")), h.get(iid("IWF")), h.get(iid("SHY"))
    if not v or not g or not b:
        return {}
    rv, rg = _ret(v, lookback), _ret(g, lookback)
    if rv is None or rg is None or max(rv, rg) <= 0:
        return {iid("SHY"): CB}
    return {iid("IWD") if rv >= rg else iid("IWF"): CB}


def credit_signal(h: Hist, sma: int = 100) -> dict[str, float]:
    hy, lq, s, t = (h.get(iid(x)) for x in ("HYG", "LQD", "SPY", "IEF"))
    if not (hy and lq and s and t):
        return {}
    n = min(len(hy), len(lq))
    if n < sma:
        return {}
    ratio = [hy[-n + k].close / lq[-n + k].close for k in range(n)]
    return {iid("SPY"): CB} if ratio[-1] > sum(ratio[-sma:]) / sma else {iid("IEF"): CB}


def absolute_momentum(h: Hist, lookback: int = 252) -> dict[str, float]:
    s, b = h.get(iid("SPY")), h.get(iid("SHY"))
    r = _ret(s, lookback) if s else None
    if r is None or not b:
        return {}
    return {iid("SPY"): CB} if r > 0 else {iid("SHY"): CB}


def sector_breadth(h: Hist, sma: int = 200) -> dict[str, float]:
    sec = [iid(x) for x in "XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()]
    on = [i for i in sec if i in h and (m := _sma(h[i], sma)) is not None and h[i][-1].close > m]
    if not h.get(iid("SHY")) or any(i in h and len(h[i]) < sma for i in sec):
        return {}
    w = {i: CB / len(sec) for i in on}
    if len(on) < len(sec):
        w[iid("SHY")] = CB * (len(sec) - len(on)) / len(sec)
    return w


def permanent_portfolio(h: Hist) -> dict[str, float]:
    assets = [iid(x) for x in "SPY TLT GLD SHY".split()]
    return {i: CB / 4 for i in assets if i in h}


def low_vol_sectors(h: Hist, window: int = 63, top: int = 3) -> dict[str, float]:
    sec = [iid(x) for x in "XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()]
    sc = sorted((v, i) for i in sec if i in h and (v := _vol(h[i], window)))[:top]
    return {i: CB / top for _, i in sc}


def sector_reversal(h: Hist, lookback: int = 21, top: int = 3) -> dict[str, float]:
    sec = [iid(x) for x in "XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()]
    sc = sorted((r, i) for i in sec if i in h and (r := _ret(h[i], lookback)) is not None)[:top]
    return {i: CB / top for _, i in sc}


def bond_rotation(h: Hist, lookback: int = 126) -> dict[str, float]:
    assets = [iid(x) for x in "TLT IEF LQD HYG".split()]
    sc = sorted(((_ret(h[i], lookback), i) for i in assets if i in h and _ret(h[i], lookback) is not None), reverse=True)
    if not sc or not h.get(iid("SHY")):
        return {}
    return {sc[0][1]: CB} if sc[0][0] > 0 else {iid("SHY"): CB}


def defensive_cyclical(h: Hist, lookback: int = 126) -> dict[str, float]:
    d = [iid(x) for x in "XLP XLU XLV".split()]
    c = [iid(x) for x in "XLY XLK XLI".split()]
    if not all(i in h for i in d + c):
        return {}
    rd = [_ret(h[i], lookback) for i in d]
    rc = [_ret(h[i], lookback) for i in c]
    if None in rd or None in rc:
        return {}
    pick = d if sum(rd) > sum(rc) else c
    return {i: CB / 3 for i in pick}


def golden_cross(h: Hist, fast: int = 50, slow: int = 200) -> dict[str, float]:
    s, b = h.get(iid("SPY")), h.get(iid("SHY"))
    f, sl = (_sma(s, fast), _sma(s, slow)) if s else (None, None)
    if f is None or sl is None or not b:
        return {}
    return {iid("SPY"): CB} if f > sl else {iid("SHY"): CB}



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
    _c("N11_value_growth", "Value versus growth style rotation",
       "Style momentum (Barberis and Shleifer; Chen and De Bondt): styles that outperformed recently tend to keep doing so for months.",
       "Monthly: hold IWD (value) or IWF (growth), whichever has the higher 126-session return, if positive; otherwise SHY.", "IWD IWF SHY",
       value_growth, [partial(value_growth, lookback=63), partial(value_growth, lookback=189)]),
    _c("N12_credit_risk_signal", "High-yield credit as an equity risk signal",
       "Credit markets lead equities (Gilchrist and Zakrajsek): when high-yield bonds weaken against investment grade, risk appetite is falling.",
       "Monthly: hold SPY while the HYG/LQD price ratio is above its 100-session average, otherwise IEF.", "HYG LQD SPY IEF",
       credit_signal, [partial(credit_signal, sma=63), partial(credit_signal, sma=150)]),
    _c("N13_absolute_momentum", "S&P 500 12-month absolute momentum",
       "Time-series momentum (Moskowitz, Ooi, Pedersen): an asset's own past 12-month excess return predicts the next months.",
       "Monthly: hold SPY if its 252-session return is positive, otherwise SHY.", "SPY SHY",
       absolute_momentum, [partial(absolute_momentum, lookback=189), partial(absolute_momentum, lookback=315)]),
    _c("N14_sector_breadth", "Sector trend breadth",
       "Breadth of participation confirms trends: each sector above its own long-term average is held, the rest of that slice sits in short bonds.",
       "Monthly: nine sector ETFs, 1/9 each while above their 200-session average, the slice of any sector below it goes to SHY.", "XLB XLE XLF XLI XLK XLP XLU XLV XLY SHY",
       sector_breadth, [partial(sector_breadth, sma=150), partial(sector_breadth, sma=250)]),
    _c("N15_permanent_portfolio", "Permanent portfolio (fixed 25% mix)",
       "Browne's permanent portfolio: equal parts stocks, long bonds, gold and cash so that some part does well in every regime. No forecast used.",
       "Monthly: hold SPY, TLT, GLD, SHY at 1/4 each.", "SPY TLT GLD SHY",
       permanent_portfolio, [partial(permanent_portfolio)]),
    _c("N16_low_vol_sectors", "Low-volatility sectors",
       "The low-volatility anomaly (Ang, Hodrick, Xing, Zhang; Frazzini and Pedersen): calmer assets earn better risk-adjusted returns than volatile ones.",
       "Monthly: hold the 3 of 9 sector ETFs with the lowest 63-session volatility, equal weight.", "XLB XLE XLF XLI XLK XLP XLU XLV XLY",
       low_vol_sectors, [partial(low_vol_sectors, window=42), partial(low_vol_sectors, window=126), partial(low_vol_sectors, top=2), partial(low_vol_sectors, top=4)]),
    _c("N17_sector_reversal", "Short-term sector reversal",
       "Short-horizon reversal (Jegadeesh; Lo and MacKinlay): last month's losers tend to rebound next month, strongest in liquidity-driven moves.",
       "Monthly: hold the 3 of 9 sector ETFs with the worst 21-session return, equal weight.", "XLB XLE XLF XLI XLK XLP XLU XLV XLY",
       sector_reversal, [partial(sector_reversal, lookback=10), partial(sector_reversal, lookback=42), partial(sector_reversal, top=2), partial(sector_reversal, top=4)]),
    _c("N18_bond_rotation", "Bond sector momentum",
       "Momentum in fixed income (Jostova et al.): the bond segment with the best recent return, long Treasuries, intermediate, investment grade or high yield, keeps leading.",
       "Monthly: hold whichever of TLT, IEF, LQD, HYG has the best 126-session return if positive, otherwise SHY.", "TLT IEF LQD HYG SHY",
       bond_rotation, [partial(bond_rotation, lookback=63), partial(bond_rotation, lookback=189)]),
    _c("N19_defensive_cyclical", "Defensive versus cyclical sector tilt",
       "Sector rotation across the business cycle (Stovall; Conover et al.): defensive sectors lead when growth worries rise, cyclicals when it recovers.",
       "Monthly: hold XLP, XLU, XLV or XLY, XLK, XLI (1/3 each), whichever group had the higher 126-session average return.", "XLP XLU XLV XLY XLK XLI",
       defensive_cyclical, [partial(defensive_cyclical, lookback=63), partial(defensive_cyclical, lookback=189)]),
    _c("N20_golden_cross", "S&P 500 50/200 moving-average crossover",
       "The classic crossover trend rule (Brock, Lakonishok, LeBaron): the 50-session average above the 200-session average marks an uptrend.",
       "Monthly: hold SPY while its 50-session average is above its 200-session average, otherwise SHY.", "SPY SHY",
       golden_cross, [partial(golden_cross, fast=30), partial(golden_cross, slow=250)]),
]
