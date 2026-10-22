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
