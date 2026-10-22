"""Forward shadow record for the low-accruals rule of round 25 (research/r25-quality-2026-10-20.md, hypothesis 177).

At each month-end close from the rule's start date: score every point-in-time S&P 500 member that is also a current
member with SEC annual-report data by minus (net income - cash from operations) / total assets, from the latest 10-K
whose first-filed values were filed strictly before the decision day (fiscal year ending within the last 455 days);
hold the 20% with the highest score, equal weight, filled at that close; at least 20 scored names or the shadow holds
cash. Benchmark: equal weight of the scored names. Costs 5 bps on turnover.

Each decision is written once to paper/<rule>/decisions/<date>.json (picks, scored names, closes) and later runs reuse
the file, so the record cannot drift and the SEC data is only downloaded when a new decision date needs scoring.
Nothing here ever sends an order.
"""

import numpy as np
import pandas as pd

from core.paper_runner import COST_BPS, DataNotReady, _read_json, _write_json, decision_dates
from core.portfolio import simulate
from core.universe import members_on

MIN_SCORED = 20
FRACTION = 0.2


def fetch_facts() -> pd.DataFrame:
    from research.round25_data import fetch
    frame = fetch()
    for col in ("start", "end", "filed"):
        frame[col] = pd.to_datetime(frame[col])
    return frame


def score_decision(date, priced, tables):
    """Names with an accruals score and the picks (highest minus-accruals first)."""
    from research.round25_tests import scores_at
    scores = pd.Series({t: scores_at(tables, t, date)[1] for t in priced}).dropna()
    if len(scores) < MIN_SCORED:
        return sorted(scores.index), []
    n = max(1, int(round(FRACTION * len(scores))))
    picks = [t for t, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]
    return sorted(scores.index), sorted(picks)


def run_accruals_rule(cfg: dict, session: pd.Timestamp, membership: pd.Series, fetch, out_dir, facts=None) -> dict:
    """Update the shadow record of one tracked low-accruals rule up to `session`. out_dir=None writes nothing."""
    start = pd.Timestamp(cfg["start"])
    decisions = decision_dates(start, session)
    status = {"rule": cfg["rule"], "asof": str(session.date()), "start": str(start.date()),
              "membership_last_row": str(membership.index[-1].date())}
    if not decisions:
        status |= {"state": "waiting", "first_decision": str(decision_dates(start, start + pd.Timedelta(days=40))[0].date())}
        _write_json(out_dir, "status.json", status)
        return status

    recorded = {d: _read_json(out_dir, f"decisions/{d.date()}.json") for d in decisions}
    members = sorted(frozenset().union(*members_on(membership, decisions)))
    closes = fetch(members, start - pd.Timedelta(days=5), session)
    index = closes.dropna(how="all").index
    if index[-1] < session:
        raise DataNotReady(f"latest bar is {index[-1].date()}, but the last completed session is {session.date()}")
    tables = None
    for date in decisions:
        if recorded[date] is not None:
            continue
        if date not in index:
            raise DataNotReady(f"no bar for decision date {date.date()}")
        if tables is None:
            from research.round25_tests import annual_tables
            tables = annual_tables(facts if facts is not None else fetch_facts())
        priced = [t for t in sorted(members_on(membership, [date])[0]) if t in closes.columns and pd.notna(closes.at[date, t])]
        scored, picks = score_decision(date, priced, tables)
        record = {"decision_date": str(date.date()), "rule": cfg["rule"], "members": len(members_on(membership, [date])[0]),
                  "priced": len(priced), "scored": scored, "picks": picks, "weight_each": 1.0 / len(picks) if picks else 0.0,
                  "closes": {t: float(closes.at[date, t]) for t in sorted(set(picks) | set(scored))}}
        _write_json(out_dir, f"decisions/{date.date()}.json", record)
        recorded[date] = record

    closes = closes.reindex(index)
    targets = pd.DataFrame(np.nan, index, closes.columns)
    bench = targets.copy()
    for date in decisions:
        rec = recorded[date]
        targets.loc[date] = 0.0
        bench.loc[date] = 0.0
        if rec["picks"]:
            targets.loc[date, rec["picks"]] = 1.0 / len(rec["picks"])
        if rec["scored"]:
            bench.loc[date, rec["scored"]] = 1.0 / len(rec["scored"])
    first = decisions[0]
    close_ff = closes.ffill().loc[first:]
    initial = float(cfg.get("initial_cash", 100_000))
    run, bm = simulate(close_ff, targets.loc[first:], COST_BPS), simulate(close_ff, bench.loc[first:], COST_BPS)
    nav = pd.DataFrame({"nav": initial * (1 + run["returns"]).cumprod(), "benchmark_nav": initial * (1 + bm["returns"]).cumprod(),
                        "invested": run["held"]})
    nav.index.name = "date"
    last = recorded[decisions[-1]]
    status |= {"state": "running", "first_decision": str(first.date()), "last_decision": str(decisions[-1].date()),
               "decisions": len(decisions), "nav": float(nav["nav"].iloc[-1]), "benchmark_nav": float(nav["benchmark_nav"].iloc[-1]),
               "excess_return": float(nav["nav"].iloc[-1] / nav["benchmark_nav"].iloc[-1] - 1),
               "total_return": float(nav["nav"].iloc[-1] / initial - 1), "holdings": last["picks"], "scored": len(last["scored"])}
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        nav.to_csv(out_dir / "nav.csv")
    _write_json(out_dir, "status.json", status)
    return status
