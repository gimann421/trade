"""Forward shadow record for the low-accruals rule of round 25 (research/r25-quality-2026-10-20.md, hypothesis 177).

At each month-end close from the rule's start date: score every point-in-time S&P 500 member that is also a current
member with SEC annual-report data by minus (net income - cash from operations) / total assets, from the latest 10-K
whose first-filed values were filed strictly before the decision day (fiscal year ending within the last 455 days);
hold the 20% with the highest score, equal weight, filled at that close; at least 20 scored names or the shadow holds
cash. Benchmark: equal weight of the scored names. Costs 5 bps on turnover.

Each decision is written once to paper/<rule>/decisions/<date>.json (picks, scored names, closes) and later runs reuse
the file, so the record cannot drift and the SEC data is only downloaded when a new decision date needs scoring.
Nothing here ever sends an order.

The same record runs the R&D intensity rule of round 28 (research/r28-leverage-rnd-stability-2026-10-22.md, hypothesis 189):
hold the 20% of scored members with the highest R&D expense / total assets (fiscal-year values filed before the decision),
benchmark equal weight of the scored (R&D-reporting) names. Sector caveat, written into its status.json: the picks are
almost all technology, health-care and chemicals names, and the backtest edge outside them was nil in 2017-22.

The third rule is sales/price of round 36 (research/r36-value-yields-2026-10-29.md, hypothesis 218): hold the 20% of scored
members with the highest annual revenue / market value, where market value is shares outstanding (10-K cover page, else
weighted diluted) x the unadjusted close on the filing day, carried forward by the adjusted-close ratio to the decision day.
Garret approved a shadow record and a paper sleeve for it on 2026-11-01.

The fourth rule is the round 57 near miss (research/r57-pension-debtflow-2026-10-30.md): hold the 20% of scored members with the
HIGHEST net long-term debt issuance (debt proceeds minus repayments over the latest fiscal year) / total assets. It was found
as an unregistered mirror of the pre-registered low-issuance rule, so it is an unconfirmed lead; Garret asked for a shadow
record only (2026-11-01), no orders.
"""

import numpy as np
import pandas as pd

from core.config import ROOT
from core.paper_runner import COST_BPS, DataNotReady, _read_json, _write_json, decision_dates
from core.portfolio import simulate
from core.universe import members_on

MIN_SCORED = 20
FRACTION = 0.2
DEFAULT_RULE = "lowaccruals_quintile"
RND_RULE = "rnd_quintile"
SP_RULE = "salesprice_quintile"
DEBT_RULE = "debtissuance_quintile"
PRO, REP = "ProceedsFromIssuanceOfLongTermDebt", "RepaymentsOfLongTermDebt"
DEBT_TAGS = ("Assets", PRO, REP)
SP_TAGS = ("Assets", "Liabilities", "NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities",
           "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax")
HISTORY_DAYS = 520          # the sales/price score needs closes back to the 10-K filing day (fiscal year ends up to 455 days back)
CAVEATS = {DEBT_RULE: "Unconfirmed lead: the mirror of a pre-registered rule, found after the results were seen (in-sample placebo 0.91, below the 0.95 bar; "
                       "OOS +6.1%). Universe is current S&P 500 members that report debt proceeds or repayments (survivorship). 263 hypotheses tested.",
           SP_RULE: "Weaker pass: mostly an industry tilt (industry-neutral version +1.1% / +1.7%), book/price was negative, within-industry "
                    "2017-22 edge was -1.2%. Universe is current S&P 500 members with SEC revenue and share data (survivorship). 218 hypotheses tested.",
           RND_RULE: "Picks are almost all technology, health-care and chemicals names (SIC 28, 35-38, 73); outside them the 2017-22 "
                     "backtest edge was +0.6%. Universe is current S&P 500 members with an R&D tag (survivorship). 190 hypotheses tested."}


def fetch_facts(rule: str = DEFAULT_RULE):
    from research.round25_data import fetch
    if rule == SP_RULE:
        from research import round36_data
        frame = fetch(tags=SP_TAGS, out=ROOT / "data" / "tracker_sp")
        round36_data.OUT = ROOT / "data" / "tracker_sp_shares"
        shares = round36_data.fetch_shares()
        for df in (frame, shares):
            for col in ("start", "end", "filed"):
                df[col] = pd.to_datetime(df[col])
        return {"facts": frame, "shares": shares}
    if rule == DEBT_RULE:
        frame = fetch(tags=DEBT_TAGS, out=ROOT / "data" / "tracker_debt")
    elif rule == RND_RULE:
        frame = fetch(tags=("Assets", "ResearchAndDevelopmentExpense"), out=ROOT / "data" / "tracker_rnd")
    else:
        frame = fetch()
    for col in ("start", "end", "filed"):
        frame[col] = pd.to_datetime(frame[col])
    return frame


def build_sp_tables(bundle: dict, closes: pd.DataFrame, raw: pd.DataFrame):
    """Round 36 value tables from SEC facts, shares and the adjusted and unadjusted closes: (value tables, adjusted closes by name)."""
    from research import round27_data
    from research.round25_tests import annual_tables
    from research.round28_tests import tables_from
    from research.round36_tests import value_tables
    facts = bundle["facts"]
    adj = {t: closes[t].dropna() for t in closes.columns}
    raw_bars = {t: pd.DataFrame({"close": raw[t].dropna()}) for t in raw.columns}
    original, round27_data.load_facts = round27_data.load_facts, lambda: facts
    try:
        vt = value_tables(annual_tables(facts), tables_from(facts), bundle["shares"], raw_bars, adj)
    finally:
        round27_data.load_facts = original
    return {"vt": vt, "adj": adj}


def build_tables(facts: pd.DataFrame, rule: str = DEFAULT_RULE):
    if rule == RND_RULE:
        from research.round28_tests import tables_from
        return tables_from(facts)
    from research.round25_tests import annual_tables
    return annual_tables(facts)


def debt_score(tables, ticker, date) -> float:
    """Net long-term debt issuance / assets for the latest fiscal year filed before `date`; NaN if neither leg is reported that year."""
    wide = tables.get(ticker)
    if wide is None:
        return float("nan")
    ok = wide[(wide["avail"] < date) & (wide.index >= date - pd.Timedelta(days=455)) & wide["assets"].notna() & (wide["assets"] > 0)]
    if ok.empty:
        return float("nan")
    r = ok.iloc[-1]
    legs = [r[c] if c in ok.columns else np.nan for c in (PRO, REP)]
    if all(pd.isna(v) for v in legs):
        return float("nan")
    return float((0.0 if pd.isna(legs[0]) else legs[0]) - (0.0 if pd.isna(legs[1]) else legs[1])) / r["assets"]


def score_one(tables, ticker, date, rule: str = DEFAULT_RULE) -> float:
    if rule == DEBT_RULE:
        return debt_score(tables, ticker, date)
    if rule == SP_RULE:
        from research.round36_tests import scores
        return scores(tables["vt"], tables["adj"], ticker, date)["sp"] if ticker in tables["adj"] else float("nan")
    if rule == RND_RULE:
        from research.round28_tests import scores
        return scores(tables, ticker, date)["rnd"]
    from research.round25_tests import scores_at
    return scores_at(tables, ticker, date)[1]


def score_decision(date, priced, tables, rule: str = DEFAULT_RULE):
    """Names with a score and the picks (highest score first: minus-accruals, or R&D over assets)."""
    scores = pd.Series({t: score_one(tables, t, date, rule) for t in priced}).dropna()
    if len(scores) < MIN_SCORED:
        return sorted(scores.index), []
    n = max(1, int(round(FRACTION * len(scores))))
    picks = [t for t, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]
    return sorted(scores.index), sorted(picks)


def run_accruals_rule(cfg: dict, session: pd.Timestamp, membership: pd.Series, fetch, out_dir, facts=None) -> dict:
    """Update the shadow record of one tracked low-accruals rule up to `session`. out_dir=None writes nothing."""
    rule = cfg.get("strategy_rule", DEFAULT_RULE)
    start = pd.Timestamp(cfg["start"])
    decisions = decision_dates(start, session)
    status = {"rule": cfg["rule"], "strategy_rule": rule, **({"caveat": CAVEATS[rule]} if rule in CAVEATS else {}), "asof": str(session.date()), "start": str(start.date()),
              "membership_last_row": str(membership.index[-1].date())}
    if not decisions:
        status |= {"state": "waiting", "first_decision": str(decision_dates(start, start + pd.Timedelta(days=40))[0].date())}
        _write_json(out_dir, "status.json", status)
        return status

    recorded = {d: _read_json(out_dir, f"decisions/{d.date()}.json") for d in decisions}
    members = sorted(frozenset().union(*members_on(membership, decisions)))
    lead = HISTORY_DAYS if rule == SP_RULE else 5
    closes = fetch(members, start - pd.Timedelta(days=lead), session)
    index = closes.dropna(how="all").index
    if index[-1] < session:
        raise DataNotReady(f"latest bar is {index[-1].date()}, but the last completed session is {session.date()}")
    tables = None
    for date in decisions:
        if recorded[date] is not None:
            continue
        if date not in index:
            raise DataNotReady(f"no bar for decision date {date.date()}")
        if tables is None and rule == SP_RULE:
            bundle = facts if facts is not None else fetch_facts(rule)
            tables = build_sp_tables(bundle, closes, fetch(members, start - pd.Timedelta(days=lead), session, raw=True))
        elif tables is None:
            tables = build_tables(facts if facts is not None else fetch_facts(rule), rule)
        priced = [t for t in sorted(members_on(membership, [date])[0]) if t in closes.columns and pd.notna(closes.at[date, t])]
        scored, picks = score_decision(date, priced, tables, rule)
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
