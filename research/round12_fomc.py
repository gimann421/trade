"""Hypothesis 125: pre-FOMC drift in SPY (research/r12-vix-residual-volume-fomc-2026-10-15.md, rule B6).

    PYTHONPATH=. python research/round12_fomc.py

Hold SPY from the 16:00 close of the session before a scheduled FOMC announcement to the 14:00 price on the
announcement day. Statement dates are read from federalreserve.gov; unscheduled actions are dropped.
"""

import json
import re
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.config import ROOT, load_paper_keys
from core.data import DATA_DIR
from core.ledger import add_evidence, add_hypothesis, connect, set_status, set_strategy
from research.round6_scan import lookup
from research.round8_short_horizon import DIRTY, PLACEBO, WINDOWS

MEMO = "research/r12-vix-residual-volume-fomc-2026-10-15.md"
TITLE = "Pre-FOMC drift: spy_prefomc"
UNSCHEDULED = {"2019-10-11", "2020-03-03", "2020-03-15", "2020-03-23", "2020-03-31", "2025-08-22"}
BAR_BPS, STRESS_COST_BPS, COST_BPS = 25.0, 10.0, 5.0
PAGES = ["https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"] + [
    f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm" for y in (2017, 2018, 2019, 2020)]
OUT = ROOT / "backtests" / "round12_fomc"


def fomc_dates() -> list[pd.Timestamp]:
    found = set()
    for url in PAGES:
        text = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "trade-research"}), timeout=60).read().decode("utf8", "ignore")
        found |= set(re.findall(r"monetary(20\d{6})a\.htm", text))
    dates = sorted(pd.Timestamp(d) for d in found if f"{d[:4]}-{d[4:6]}-{d[6:]}" not in UNSCHEDULED)
    return [d for d in dates if d >= pd.Timestamp("2017-01-02") and d <= pd.Timestamp.now().normalize()]


def spy_snapshots() -> pd.DataFrame:
    """Per session: last 16:00 close and the 14:00 price (close of the 13:45 bar), adjustment ALL, from Alpaca."""
    path = DATA_DIR / "spy_1400.csv"
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True)
    from alpaca.data.enums import Adjustment
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    keys = load_paper_keys()
    client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    request = StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame(15, TimeFrameUnit.Minute),
                               start=datetime(2016, 12, 1, tzinfo=timezone.utc),
                               end=pd.Timestamp.now("UTC").to_pydatetime() - pd.Timedelta(minutes=20), adjustment=Adjustment.ALL)
    df = client.get_stock_bars(request).df
    df = df.xs("SPY", level="symbol") if isinstance(df.index, pd.MultiIndex) else df
    df.index = pd.to_datetime(df.index).tz_convert("America/New_York")
    minutes = df.index.hour * 60 + df.index.minute
    day = pd.Series(df.index.date, index=df.index)
    out = pd.DataFrame({"p1400": df["close"][minutes == 13 * 60 + 45].groupby(day[minutes == 13 * 60 + 45].values).last(),
                        "close": df["close"][minutes == 15 * 60 + 45].groupby(day[minutes == 15 * 60 + 45].values).last()})
    out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    out.to_csv(path)
    return out


def main():
    snaps = spy_snapshots().dropna()
    window_ret = (snaps["p1400"] / snaps["close"].shift(1) - 1).dropna()       # previous close to 14:00 of the day
    dirty = pd.date_range(DIRTY[0], DIRTY[1])
    events = [d for d in fomc_dates() if d in window_ret.index and d not in dirty]
    ordinary = window_ret[~window_ret.index.isin(events) & ~window_ret.index.isin(dirty)]
    rng = np.random.default_rng(PLACEBO["seed"])
    results = {}
    for label, (start, end) in WINDOWS.items():
        lo, hi = max(pd.Timestamp(start), pd.Timestamp("2017-01-02")), pd.Timestamp(end) if end else pd.Timestamp("2100-01-01")
        ev = window_ret.loc[[d for d in events if lo <= d <= hi]]
        pool = ordinary.loc[lo:hi].to_numpy()
        gross = float(ev.mean())
        draws = np.array([rng.choice(pool, size=len(ev), replace=False).mean() for _ in range(PLACEBO["n"])])
        pct = float((draws < gross).mean())
        net = lambda bps: (gross - 2 * bps / 1e4) * 1e4
        years = (min(hi, window_ret.index[-1]) - lo).days / 365.25
        results[label] = {"events": len(ev), "gross_bps": gross * 1e4, "net_bps": net(COST_BPS), "stress_net_bps": net(STRESS_COST_BPS),
                          "placebo": pct, "events_per_year": len(ev) / years, "random_window_mean_bps": float(pool.mean() * 1e4),
                          "hit_rate": float((ev > 0).mean()), "start": str(ev.index[0].date()), "end": str(ev.index[-1].date())}
        r = results[label]
        reasons = []
        if r["net_bps"] < BAR_BPS:
            reasons.append(f"net {r['net_bps']:.1f} bps per event < {BAR_BPS:.0f}")
        if pct < PLACEBO_THRESHOLD:
            reasons.append(f"placebo {pct:.3f} < 0.95")
        if r["stress_net_bps"] <= 0:
            reasons.append(f"net at 10 bps per trade {r['stress_net_bps']:.1f} not above 0")
        r["verdict"] = "contradicts" if reasons else "supports"
        r["why"] = reasons or ["passes the bar and the stress check"]
        print(label, json.dumps(r, default=str))
    status = "supported" if all(r["verdict"] == "supports" for r in results.values()) else "rejected"
    conn = connect()
    ids = lookup(conn)
    if TITLE not in ids:
        ids[TITLE] = add_hypothesis(conn, TITLE,
                                    "Holding SPY from the close before each scheduled FOMC announcement to 14:00 on announcement day earns >= 25 bps net per event, "
                                    "placebo >= 0.95 and positive at 10 bps per trade, in both 2017-2022 and 2023+.",
                                    rationale="Lucca and Moench 2015; weakened after 2015 in later studies.", research_memo=MEMO)
    hid = ids[TITLE]
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"spy_prefomc_{stamp}.json"
    for w, r in results.items():
        summary = (f"spy_prefomc {w} {r['start']}..{r['end']}: {r['events']} events, gross {r['gross_bps']:.1f} bps, net {r['net_bps']:.1f} bps per event at 5 bps a trade "
                   f"(random same-window mean {r['random_window_mean_bps']:.1f} bps), placebo {r['placebo']:.3f}, 10 bps a trade {r['stress_net_bps']:.1f} bps, "
                   f"hit rate {r['hit_rate']:.0%}. {r['verdict']}: {'; '.join(r['why'])}")
        add_evidence(conn, hid, "backtest", summary, r["verdict"], ref=str(path.relative_to(ROOT)))
    set_status(conn, hid, status)
    conn.close()
    path.write_text(json.dumps({"events": [str(d.date()) for d in events], "results": results, "status": status}, indent=1) + "\n")
    print("status", status, "events", len(events))


PLACEBO_THRESHOLD = 0.95

if __name__ == "__main__":
    main()
