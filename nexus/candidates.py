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



# ---- batch 3 rules (authored before any was tested) ---------------------------------------------------------------------
def pair_rotation(h: Hist, a: str = "EEM", b: str = "EFA", lookback: int = 126) -> dict[str, float]:
    x, y, c = h.get(iid(a)), h.get(iid(b)), h.get(iid("SHY"))
    if not x or not y or not c:
        return {}
    rx, ry = _ret(x, lookback), _ret(y, lookback)
    if rx is None or ry is None or max(rx, ry) <= 0:
        return {iid("SHY"): CB}
    return {iid(a) if rx >= ry else iid(b): CB}


def single_trend(h: Hist, sym: str = "GLD", sma: int = 200) -> dict[str, float]:
    x, c = h.get(iid(sym)), h.get(iid("SHY"))
    m = _sma(x, sma) if x else None
    if m is None or not c:
        return {}
    return {iid(sym): CB} if x[-1].close > m else {iid("SHY"): CB}


def spy_tlt_inverse_vol(h: Hist, window: int = 63) -> dict[str, float]:
    s, t = h.get(iid("SPY")), h.get(iid("TLT"))
    vs, vt = (_vol(s, window), _vol(t, window)) if s and t else (None, None)
    if not vs or not vt:
        return {}
    ws, wt = 1 / vs, 1 / vt
    return {iid("SPY"): CB * ws / (ws + wt), iid("TLT"): CB * wt / (ws + wt)}


def vol_regime(h: Hist, short: int = 20, long: int = 126) -> dict[str, float]:
    s, b = h.get(iid("SPY")), h.get(iid("IEF"))
    vs, vl = (_vol(s, short), _vol(s, long)) if s and b else (None, None)
    if not vs or not vl:
        return {}
    return {iid("SPY"): CB} if vs <= vl else {iid("IEF"): CB}


def return_over_vol(h: Hist, lookback: int = 126, top: int = 4) -> dict[str, float]:
    assets = [iid(x) for x in "SPY EFA EEM TLT IEF LQD GLD VNQ".split()]
    sc = []
    for i in assets:
        if i in h:
            r, v = _ret(h[i], lookback), _vol(h[i], lookback)
            if r is not None and v:
                sc.append((r / v, r, i))
    sc.sort(reverse=True)
    pick = [i for _, r, i in sc[:top] if r > 0]
    return {i: CB / top for i in pick}


def drawdown_stop(h: Hist, window: int = 252, limit: float = 0.10) -> dict[str, float]:
    s, b = h.get(iid("SPY")), h.get(iid("SHY"))
    if not s or not b or len(s) < window:
        return {}
    peak = max(x.close for x in s[-window:])
    return {iid("SHY"): CB} if s[-1].close < peak * (1 - limit) else {iid("SPY"): CB}



# ---- batch 4 rules (authored before any was tested) ---------------------------------------------------------------------
def growth_leadership(h: Hist, lookback: int = 126) -> dict[str, float]:
    q, s, c = h.get(iid("QQQ")), h.get(iid("SPY")), h.get(iid("SHY"))
    if not q or not s or not c:
        return {}
    rq, rs = _ret(q, lookback), _ret(s, lookback)
    if rq is None or rs is None or max(rq, rs) <= 0:
        return {iid("SHY"): CB}
    return {iid("QQQ") if rq >= rs else iid("SPY"): CB}


def duration_rotation(h: Hist, lookback: int = 126) -> dict[str, float]:
    lo, sh, c = h.get(iid("TLT")), h.get(iid("IEI")), h.get(iid("SHY"))
    if not lo or not sh or not c:
        return {}
    rl, rs = _ret(lo, lookback), _ret(sh, lookback)
    if rl is None or rs is None or max(rl, rs) <= 0:
        return {iid("SHY"): CB}
    return {iid("TLT") if rl >= rs else iid("IEI"): CB}


def sell_in_may(h: Hist, start_month: int = 11, end_month: int = 4) -> dict[str, float]:
    s, c = h.get(iid("SPY")), h.get(iid("SHY"))
    if not s or not c:
        return {}
    m = int(s[-1].session_date[5:7])
    return {iid("SPY"): CB} if (m >= start_month or m <= end_month) else {iid("SHY"): CB}


def four_asset_trend(h: Hist, sma: int = 200) -> dict[str, float]:
    assets = [iid(x) for x in "SPY TLT GLD VNQ".split()]
    if not h.get(iid("SHY")) or any(i not in h or len(h[i]) < sma for i in assets):
        return {}
    w: dict[str, float] = {}
    for i in assets:
        key = i if h[i][-1].close > _sma(h[i], sma) else iid("SHY")
        w[key] = w.get(key, 0.0) + CB / 4
    return w


def inflation_rotation(h: Hist, lookback: int = 126) -> dict[str, float]:
    assets = [iid(x) for x in "GLD TLT DBC".split()]
    sc = sorted(((_ret(h[i], lookback), i) for i in assets if i in h and _ret(h[i], lookback) is not None), reverse=True)
    if not sc or not h.get(iid("SHY")):
        return {}
    return {sc[0][1]: CB} if sc[0][0] > 0 else {iid("SHY"): CB}


def calm_assets(h: Hist, window: int = 126, top: int = 3) -> dict[str, float]:
    assets = [iid(x) for x in "SPY EFA EEM TLT IEF LQD GLD VNQ".split()]
    sc = sorted((v, i) for i in assets if i in h and (v := _vol(h[i], window)) and (_ret(h[i], window) or 0) > 0)[:top]
    return {i: CB / top for _, i in sc}


def credit_trend(h: Hist, sma: int = 100) -> dict[str, float]:
    x, c = h.get(iid("HYG")), h.get(iid("SHY"))
    m = _sma(x, sma) if x else None
    if m is None or not c:
        return {}
    return {iid("HYG"): CB} if x[-1].close > m else {iid("SHY"): CB}


def sector_momentum_filtered(h: Hist, lookback: int = 126, top: int = 3, sma: int = 200) -> dict[str, float]:
    s, c = h.get(iid("SPY")), h.get(iid("SHY"))
    m = _sma(s, sma) if s else None
    if m is None or not c:
        return {}
    if s[-1].close <= m:
        return {iid("SHY"): CB}
    sec = [iid(x) for x in "XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()]
    sc = sorted(((_ret(h[i], lookback), i) for i in sec if i in h and _ret(h[i], lookback) is not None), reverse=True)[:top]
    return {i: CB / top for _, i in sc}



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
    _c("N21_em_vs_developed", "Emerging versus developed markets rotation",
       "Country and regional momentum (Asness, Moskowitz, Pedersen; Rouwenhorst): the stronger region over the past months tends to stay ahead.",
       "Monthly: hold EEM or EFA, whichever has the higher 126-session return, if positive; otherwise SHY.", "EEM EFA SHY",
       pair_rotation, [partial(pair_rotation, lookback=63), partial(pair_rotation, lookback=189)]),
    _c("N22_small_vs_large", "Small versus large cap rotation",
       "Size-factor momentum (Fama and French size factor; Ehsani and Linnainmaa): the size segment that did better recently keeps its lead.",
       "Monthly: hold IWM or IWB, whichever has the higher 126-session return, if positive; otherwise SHY.", "IWM IWB SHY",
       partial(pair_rotation, a="IWM", b="IWB"), [partial(pair_rotation, a="IWM", b="IWB", lookback=63), partial(pair_rotation, a="IWM", b="IWB", lookback=189)]),
    _c("N23_gold_trend", "Gold trend filter",
       "Trend following works in commodities (Hurst, Ooi, Pedersen): gold has long multi-month trends driven by real-rate and fear cycles.",
       "Monthly: hold GLD while above its 200-session average, otherwise SHY.", "GLD SHY",
       single_trend, [partial(single_trend, sma=150), partial(single_trend, sma=250)]),
    _c("N24_commodity_trend", "Broad commodity trend filter",
       "Commodity futures show strong time-series momentum (Miffre and Rallis; Gorton and Rouwenhorst); the filter avoids long bear phases.",
       "Monthly: hold DBC while above its 200-session average, otherwise SHY.", "DBC SHY",
       partial(single_trend, sym="DBC"), [partial(single_trend, sym="DBC", sma=150), partial(single_trend, sym="DBC", sma=250)]),
    _c("N25_reit_trend", "Listed real estate trend filter",
       "Real estate returns trend and are cyclical with credit conditions; a trend filter sidesteps large REIT drawdowns.",
       "Monthly: hold VNQ while above its 200-session average, otherwise SHY.", "VNQ SHY",
       partial(single_trend, sym="VNQ"), [partial(single_trend, sym="VNQ", sma=150), partial(single_trend, sym="VNQ", sma=250)]),
    _c("N26_long_bond_trend", "Long Treasury trend filter",
       "Bond trends follow the monetary cycle (Hurst, Ooi, Pedersen): long bonds spend years rising or falling, and trend rules capture part of that.",
       "Monthly: hold TLT while above its 200-session average, otherwise SHY.", "TLT SHY",
       partial(single_trend, sym="TLT"), [partial(single_trend, sym="TLT", sma=150), partial(single_trend, sym="TLT", sma=250)]),
    _c("N27_stock_bond_inverse_vol", "Stock and long-bond risk balance",
       "Risk parity (Qian; Asness, Frazzini, Pedersen): weighting stocks and bonds so each contributes similar risk, with no forecast.",
       "Monthly: SPY and TLT weighted by 1/volatility (63 sessions), summing to 99%.", "SPY TLT",
       spy_tlt_inverse_vol, [partial(spy_tlt_inverse_vol, window=42), partial(spy_tlt_inverse_vol, window=126)]),
    _c("N28_volatility_regime", "Volatility regime switch",
       "Volatility clusters (Engle; Moreira and Muir): when recent volatility rises above its long-run level, risk assets tend to do worse.",
       "Monthly: hold SPY while its 20-session volatility is at or below its 126-session volatility, otherwise IEF.", "SPY IEF",
       vol_regime, [partial(vol_regime, short=10), partial(vol_regime, long=252)]),
    _c("N29_return_over_volatility", "Risk-adjusted multi-asset momentum",
       "Momentum scaled by volatility (Barroso and Santa-Clara; Moskowitz et al.): ranking by return per unit of risk avoids chasing volatile winners.",
       "Monthly: of SPY, EFA, EEM, TLT, IEF, LQD, GLD, VNQ hold the 4 with the best 126-session return/volatility, only those with positive return.", "SPY EFA EEM TLT IEF LQD GLD VNQ",
       return_over_vol, [partial(return_over_vol, lookback=63), partial(return_over_vol, lookback=189), partial(return_over_vol, top=3), partial(return_over_vol, top=5)]),
    _c("N30_drawdown_stop", "S&P 500 drawdown stop",
       "Loss aversion and crash clustering (Daniel and Moskowitz): after a 10% fall from the 12-month high, further large losses are more likely than usual.",
       "Monthly: hold SPY unless it closes more than 10% below its 252-session high, then SHY.", "SPY SHY",
       drawdown_stop, [partial(drawdown_stop, limit=0.08), partial(drawdown_stop, limit=0.12)]),
    _c("N31_growth_leadership", "Nasdaq-100 versus S&P 500 leadership",
       "Style and sector leadership persists (Moskowitz and Grinblatt): growth-heavy indexes that lead tend to keep leading over the next months.",
       "Monthly: hold QQQ or SPY, whichever has the higher 126-session return, if positive; otherwise SHY.", "QQQ SPY SHY",
       growth_leadership, [partial(growth_leadership, lookback=63), partial(growth_leadership, lookback=189)]),
    _c("N32_duration_rotation", "Long versus intermediate Treasury rotation",
       "Duration timing follows the rate cycle (Ilmanen): the maturity that performed better recently tends to keep doing so while yields trend.",
       "Monthly: hold TLT or IEI, whichever has the higher 126-session return, if positive; otherwise SHY.", "TLT IEI SHY",
       duration_rotation, [partial(duration_rotation, lookback=63), partial(duration_rotation, lookback=189)]),
    _c("N33_sell_in_may", "Halloween indicator (sell in May)",
       "Seasonality in stock returns (Bouman and Jacobsen 2002): returns from November to April have historically exceeded May to October across many markets.",
       "Monthly: hold SPY in November through April, SHY in May through October.", "SPY SHY",
       sell_in_may, [partial(sell_in_may, start_month=10), partial(sell_in_may, end_month=5)]),
    _c("N34_four_asset_trend", "Trend-filtered stocks, long bonds, gold and real estate",
       "Faber-style timing applied to the permanent-portfolio style mix: four uncorrelated assets, each held only in an uptrend.",
       "Monthly: SPY, TLT, GLD, VNQ at 1/4 each while above their 200-session average, otherwise that quarter sits in SHY.", "SPY TLT GLD VNQ SHY",
       four_asset_trend, [partial(four_asset_trend, sma=150), partial(four_asset_trend, sma=250)]),
    _c("N35_inflation_rotation", "Inflation-hedge asset rotation",
       "Real-asset momentum (Erb and Harvey): gold, commodities and long bonds take turns as the best response to changing inflation and growth.",
       "Monthly: hold whichever of GLD, TLT, DBC has the best 126-session return if positive, otherwise SHY.", "GLD TLT DBC SHY",
       inflation_rotation, [partial(inflation_rotation, lookback=63), partial(inflation_rotation, lookback=189)]),
    _c("N36_calm_rising_assets", "Calm rising assets",
       "Low risk with positive trend (Baker, Bradley, Wurgler; Frazzini and Pedersen): low-volatility assets in an uptrend have given high return per unit of risk.",
       "Monthly: of SPY, EFA, EEM, TLT, IEF, LQD, GLD, VNQ with a positive 126-session return, hold the 3 with the lowest 126-session volatility.", "SPY EFA EEM TLT IEF LQD GLD VNQ",
       calm_assets, [partial(calm_assets, window=63), partial(calm_assets, window=189), partial(calm_assets, top=2), partial(calm_assets, top=4)]),
    _c("N37_sector_momentum_trend_gate", "Sector momentum with a market trend gate",
       "Momentum crashes happen in bear markets (Daniel and Moskowitz); gating on the market trend is a published remedy.",
       "Monthly: if SPY is above its 200-session average hold the 3 of 9 sector ETFs with the best 126-session return, otherwise SHY.", "SPY XLB XLE XLF XLI XLK XLP XLU XLV XLY SHY",
       sector_momentum_filtered, [partial(sector_momentum_filtered, lookback=63), partial(sector_momentum_filtered, lookback=189), partial(sector_momentum_filtered, sma=150), partial(sector_momentum_filtered, sma=250)]),
    _c("N38_high_yield_trend", "High-yield bond trend filter",
       "High-yield bonds behave like equity-lite plus carry and fall hard in credit stress; a trend filter avoids the worst of it (Faber).",
       "Monthly: hold HYG while above its 100-session average, otherwise SHY.", "HYG SHY",
       credit_trend, [partial(credit_trend, sma=63), partial(credit_trend, sma=150)]),
]
