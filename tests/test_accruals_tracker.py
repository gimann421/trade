import json

import numpy as np
import pandas as pd

from core import accruals_tracker as at
from core.market_calendar import trading_days


def facts(symbols, filed="2025-03-01", end="2024-12-31"):
    rows = []
    for i, s in enumerate(symbols):
        for tag, val in (("Assets", 1000.0), ("NetIncomeLoss", 100.0), ("NetCashProvidedByUsedInOperatingActivities", 100.0 + 5 * i)):
            rows.append({"symbol": s, "cik": i, "tag": tag, "start": None if tag == "Assets" else "2024-01-01", "end": end, "val": val,
                         "fy": 2024, "fp": "FY", "form": "10-K", "filed": filed})
    return pd.DataFrame(rows).astype({"start": "datetime64[ns]", "end": "datetime64[ns]", "filed": "datetime64[ns]"})


def test_picks_are_the_lowest_accruals_and_filed_before_the_decision():
    from research.round25_tests import annual_tables
    names = [f"S{i:02d}" for i in range(30)]
    tables = annual_tables(facts(names))
    scored, picks = at.score_decision(pd.Timestamp("2025-06-30"), names, tables)
    assert len(scored) == 30 and picks == [f"S{i:02d}" for i in range(24, 30)]    # cash flow rises with i, so accruals fall
    assert at.score_decision(pd.Timestamp("2025-02-28"), names, tables) == ([], [])     # the 10-K was filed after this date


def test_run_writes_decisions_once_and_nav(tmp_path):
    names = [f"S{i:02d}" for i in range(30)]
    index = trading_days("2025-01-02", "2025-08-29")
    rng = np.random.default_rng(1)
    closes = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, (len(index), 30)), axis=0), index, names)
    membership = pd.Series([frozenset(names)], index=[pd.Timestamp("2020-01-01")])
    cfg = {"rule": "stock_lowaccruals_quintile", "start": "2025-06-30", "initial_cash": 100000}
    status = at.run_accruals_rule(cfg, pd.Timestamp("2025-08-29"), membership, lambda *a, **k: closes, tmp_path, facts=facts(names))
    assert status["state"] == "running" and status["decisions"] == 3 and len(status["holdings"]) == 6
    first = json.loads((tmp_path / "decisions" / "2025-06-30.json").read_text())
    assert first["picks"] == status["holdings"] or len(first["picks"]) == 6
    again = at.run_accruals_rule(cfg, pd.Timestamp("2025-08-29"), membership, lambda *a, **k: closes, tmp_path, facts=pd.DataFrame())
    assert again["nav"] == status["nav"]                      # recorded decisions are reused; no new data needed


def rnd_facts(symbols, filed="2025-03-01", end="2024-12-31"):
    rows = []
    for i, s in enumerate(symbols):
        for tag, val in (("Assets", 1000.0), ("ResearchAndDevelopmentExpense", 10.0 + 5 * i)):
            rows.append({"symbol": s, "cik": i, "tag": tag, "start": None if tag == "Assets" else "2024-01-01", "end": end, "val": val,
                         "fy": 2024, "fp": "FY", "form": "10-K", "filed": filed})
    return pd.DataFrame(rows).astype({"start": "datetime64[ns]", "end": "datetime64[ns]", "filed": "datetime64[ns]"})


def test_rnd_rule_picks_the_highest_rnd_over_assets_and_records_the_caveat(tmp_path):
    names = [f"S{i:02d}" for i in range(30)]
    tables = at.build_tables(rnd_facts(names), at.RND_RULE)
    scored, picks = at.score_decision(pd.Timestamp("2025-06-30"), names, tables, at.RND_RULE)
    assert len(scored) == 30 and picks == [f"S{i:02d}" for i in range(24, 30)]
    assert at.score_decision(pd.Timestamp("2025-02-28"), names, tables, at.RND_RULE) == ([], [])
    index = trading_days("2025-01-02", "2025-08-29")
    rng = np.random.default_rng(2)
    closes = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, (len(index), 30)), axis=0), index, names)
    membership = pd.Series([frozenset(names)], index=[pd.Timestamp("2020-01-01")])
    cfg = {"rule": "stock_rnd_quintile", "strategy_rule": "rnd_quintile", "start": "2025-06-30", "initial_cash": 100000}
    status = at.run_accruals_rule(cfg, pd.Timestamp("2025-08-29"), membership, lambda *a, **k: closes, tmp_path, facts=rnd_facts(names))
    assert status["state"] == "running" and len(status["holdings"]) == 6 and "technology" in status["caveat"]


def sp_bundle(symbols, filed="2025-03-01", end="2024-12-31"):
    rows, share_rows = [], []
    for i, s in enumerate(symbols):
        for tag, val, flow in (("Assets", 1000.0, False), ("Liabilities", 400.0, False), ("NetIncomeLoss", 100.0, True),
                               ("NetCashProvidedByUsedInOperatingActivities", 120.0, True), ("Revenues", 500.0 + 50 * i, True)):
            rows.append({"symbol": s, "cik": i, "tag": tag, "start": "2024-01-01" if flow else None, "end": end, "val": val,
                         "fy": 2024, "fp": "FY", "form": "10-K", "filed": filed})
        share_rows.append({"symbol": s, "tag": "EntityCommonStockSharesOutstanding", "start": None, "end": "2025-02-20", "val": 10.0, "form": "10-K", "filed": filed})
    cast = {"start": "datetime64[ns]", "end": "datetime64[ns]", "filed": "datetime64[ns]"}
    return {"facts": pd.DataFrame(rows).astype(cast), "shares": pd.DataFrame(share_rows).astype(cast)}


def flat_closes(names, first="2024-12-02", last="2025-08-29"):
    index = trading_days(first, last)
    return pd.DataFrame(100.0, index, names)


def test_salesprice_rule_picks_the_highest_revenue_over_market_value(tmp_path):
    names = [f"S{i:02d}" for i in range(30)]
    closes = flat_closes(names)
    tables = at.build_sp_tables(sp_bundle(names), closes, closes)
    scored, picks = at.score_decision(pd.Timestamp("2025-06-30"), names, tables, at.SP_RULE)
    assert len(scored) == 30 and picks == [f"S{i:02d}" for i in range(24, 30)]    # same shares and price, revenue rises with i
    assert at.score_decision(pd.Timestamp("2025-02-28"), names, tables, at.SP_RULE) == ([], [])     # the 10-K was filed after this date
    membership = pd.Series([frozenset(names)], index=[pd.Timestamp("2020-01-01")])
    cfg = {"rule": "stock_salesprice_quintile", "strategy_rule": "salesprice_quintile", "start": "2025-06-30", "initial_cash": 100000}
    calls = []

    def fetch(symbols, start, end, raw=False):
        calls.append(raw)
        return closes

    status = at.run_accruals_rule(cfg, pd.Timestamp("2025-08-29"), membership, fetch, tmp_path, facts=sp_bundle(names))
    assert status["state"] == "running" and len(status["holdings"]) == 6 and "industry tilt" in status["caveat"]
    assert True in calls and False in calls                    # both unadjusted and adjusted closes were requested


def debt_facts(symbols, filed="2025-03-01", end="2024-12-31"):
    rows = []
    for i, s in enumerate(symbols):
        legs = [("Assets", 1000.0, False), ("ProceedsFromIssuanceOfLongTermDebt", 10.0 * i, True)]
        if i % 2:
            legs.append(("RepaymentsOfLongTermDebt", 5.0, True))
        for tag, val, flow in legs:
            rows.append({"symbol": s, "cik": i, "tag": tag, "start": "2024-01-01" if flow else None, "end": end, "val": val,
                         "fy": 2024, "fp": "FY", "form": "10-K", "filed": filed})
    return pd.DataFrame(rows).astype({"start": "datetime64[ns]", "end": "datetime64[ns]", "filed": "datetime64[ns]"})


def test_debt_rule_picks_the_highest_net_issuance_and_records_the_caveat(tmp_path):
    names = [f"S{i:02d}" for i in range(30)]
    tables = at.build_tables(debt_facts(names), at.DEBT_RULE)
    scored, picks = at.score_decision(pd.Timestamp("2025-06-30"), names, tables, at.DEBT_RULE)
    assert len(scored) == 30 and picks == [f"S{i:02d}" for i in range(24, 30)]
    assert at.debt_score(tables, "S01", pd.Timestamp("2025-06-30")) == (10.0 - 5.0) / 1000.0      # repayments come off the proceeds
    assert at.score_decision(pd.Timestamp("2025-02-28"), names, tables, at.DEBT_RULE) == ([], [])
    index = trading_days("2025-01-02", "2025-08-29")
    closes = pd.DataFrame(100.0, index, names)
    membership = pd.Series([frozenset(names)], index=[pd.Timestamp("2020-01-01")])
    cfg = {"rule": "stock_debtissuance_quintile", "strategy_rule": "debtissuance_quintile", "start": "2025-06-30", "initial_cash": 100000}
    status = at.run_accruals_rule(cfg, pd.Timestamp("2025-08-29"), membership, lambda *a, **k: closes, tmp_path, facts=debt_facts(names))
    assert status["state"] == "running" and len(status["holdings"]) == 6 and "Unconfirmed lead" in status["caveat"]
