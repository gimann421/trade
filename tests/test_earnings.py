import importlib.util
import json

import numpy as np
import pandas as pd
import pytest

from core import edgar
from core.config import ROOT
from core.market_calendar import trading_days

spec = importlib.util.spec_from_file_location("ed", ROOT / "strategies" / "earnings_drift_v1.py")
ed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ed)


def block(forms, items, dates=None):
    n = len(forms)
    return {"accessionNumber": [f"0001-{i}" for i in range(n)], "filingDate": dates or ["2024-01-02"] * n,
            "acceptanceDateTime": ["2024-01-02T21:05:00.000Z"] * n, "form": forms, "items": items}


def test_earnings_rows_pick_8k_with_item_202_only():
    rows = edgar.earnings_rows(block(["8-K", "8-K", "10-Q", "8-K"], ["2.02,9.01", "5.02", "2.02", "12.02"]))
    assert [r["accession"] for r in rows] == ["0001-0"]
    assert edgar.earnings_rows(block(["8-K"], [None])) == []


def test_company_events_reads_the_recent_block_and_older_pages(monkeypatch):
    monkeypatch.setattr(edgar.time, "sleep", lambda s: None)
    pages = {
        "CIK0000000123.json": {"filings": {"recent": block(["8-K"], ["2.02"]),
                                           "files": [{"name": "old-1.json", "filingTo": "2019-12-31"},
                                                     {"name": "ancient.json", "filingTo": "2009-01-01"}]}},
        "old-1.json": block(["8-K", "8-K"], ["2.02", "7.01"]),
    }
    seen = []

    def fetch(url, **kwargs):
        name = url.rsplit("/", 1)[1]
        seen.append(name)
        return json.dumps(pages[name]).encode()

    rows = edgar.company_events(123, fetch=fetch)
    assert len(rows) == 2 and "ancient.json" not in seen


def test_reaction_session_before_open_is_same_day_otherwise_next():
    sessions = pd.DatetimeIndex(trading_days("2024-05-01", "2024-05-14"))
    times = pd.Series(pd.to_datetime(["2024-05-02 11:00", "2024-05-02 21:05", "2024-05-03 20:30", "2024-05-04 15:00",
                                      "2024-05-01 13:29", "2024-05-01 13:30", "2024-05-14 22:00"], utc=True))
    # New York is UTC-4 in May: 07:00, 17:05, 16:30 Friday, Saturday 11:00, 09:29, 09:30, 18:00 on the last session
    got = edgar.reaction_sessions(times, sessions)
    assert [str(d.date()) if pd.notna(d) else None for d in got] == [
        "2024-05-02", "2024-05-03", "2024-05-06", "2024-05-06", "2024-05-01", "2024-05-02", None]


def test_qualification_uses_only_strictly_earlier_events_and_needs_history():
    rng = np.random.default_rng(0)
    pos = np.sort(np.concatenate([np.arange(0, 300, 1).repeat(2)]))  # two events a session
    ar = rng.normal(0, 0.03, len(pos))
    q = ed.qualifies(pos, ar, 80)
    assert not q[:ed.MIN_PRIOR].any()                       # not enough history yet
    assert q[ed.MIN_PRIOR:].mean() == pytest.approx(0.2, abs=0.07)
    # a later event cannot change an earlier verdict
    q_cut = ed.qualifies(pos[:300], ar[:300], 80)
    assert (q_cut == q[:300]).all()
    # events on the same session do not count as history for each other
    same = ed.qualifies(np.zeros(500, dtype=int), rng.normal(size=500), 80)
    assert not same.any()


def test_active_matrix_targets_and_hold_returns():
    index = pd.DatetimeIndex(trading_days("2024-01-02", "2024-02-29"))
    columns = ["A", "B", "C", "BIL"]
    active = ed.active_matrix((len(index), 3), np.array([3, 5]), np.array([0, 1]), hold=4)
    assert active[3:7, 0].all() and not active[2, 0] and not active[7, 0]
    assert active[5:9, 1].all() and not active[4, 1]
    targets = ed.targets_from_active(active, index, columns, start=1)
    assert targets.iloc[1]["BIL"] == 1.0 and targets.iloc[0].isna().all()           # starts in cash
    assert targets.iloc[3].to_dict() == {"A": 1.0, "B": 0.0, "C": 0.0, "BIL": 0.0}  # A enters at the close of session 3
    assert targets.iloc[5]["A"] == pytest.approx(0.5) and targets.iloc[5]["B"] == pytest.approx(0.5)
    assert targets.iloc[4].isna().all()                                              # no change, no trade
    assert targets.iloc[7]["B"] == 1.0 and targets.iloc[9]["BIL"] == 1.0              # A leaves at session 7, B at 9
    close = np.array([[100.0 * (1.01 ** t), 50.0, 20.0] for t in range(len(index))])
    market_cum = np.array([1.0005 ** t for t in range(len(index))])
    got = ed.hold_returns(close, market_cum, np.array([3, len(index) - 2]), np.array([0, 0]), hold=4)
    assert got[0] == pytest.approx(1.01 ** 4 - 1 - (1.0005 ** 4 - 1)) and np.isnan(got[1])
