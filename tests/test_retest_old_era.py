import types
from pathlib import Path

import pandas as pd
import pytest

from core import ledger, longdata
from research import retest_old_era as ro


def test_older_era_redirects_and_restores(tmp_path, monkeypatch):
    monkeypatch.setattr(ro, "OUT", tmp_path)
    module = types.SimpleNamespace(WINDOWS={"IS": ("2016-01-01", "2022-12-31")}, load_bars="original",
                                   add_evidence="original", set_status="original", set_strategy="original",
                                   save_result="original")
    with ro.older_era(module):
        assert module.WINDOWS == ro.OLD_WINDOWS and module.load_bars is ro.old_bars
        assert module.set_status(None, 1, "supported") is None and module.set_strategy(None, 1, "x.py") is None
        assert module.add_evidence is ro.tagged_add_evidence and module.save_result is ro.light_save_result
        target = tmp_path / "x" / "round9_summary.json"
        target.parent.mkdir()
        target.write_text("{}")  # redirected: lands in OUT with the old_era suffix
        assert (tmp_path / "round9_summary_old_era.json").exists() and not target.exists()
        (tmp_path / "other.json").write_text("{}")  # other files are not redirected
        assert (tmp_path / "other.json").exists()
    assert module.WINDOWS == {"IS": ("2016-01-01", "2022-12-31")} and module.load_bars == "original"
    assert module.set_status == "original" and module.add_evidence == "original" and module.save_result == "original"


def test_tagged_evidence_is_marked_and_does_not_touch_status(tmp_path):
    conn = ledger.connect(tmp_path / "ledger.db")
    hid = ledger.add_hypothesis(conn, "t", "claim")
    ledger.set_status(conn, hid, "rejected")
    ro.tagged_add_evidence(conn, hid, "backtest", "x SPY IS 2000..2015: supports", "supports")
    ro.no_op(conn, hid, "supported")
    summary, = conn.execute("SELECT summary FROM evidence WHERE hypothesis_id = ?", (hid,)).fetchone()
    assert summary.startswith(ro.TAG)
    assert conn.execute("SELECT status FROM hypotheses WHERE id = ?", (hid,)).fetchone()[0] == "rejected"


def test_collect_and_cell_keys():
    summary = {"hypotheses": {
        "14": {"status": "rejected", "cells": [{"symbol": "IWM", "window": "IS", "verdict": "supports"}]},
        "23": {"status": "rejected", "cells": [{"cell": "core IS", "verdict": "contradicts"}]},
        "32": {"status": "rejected", "cells": [{"universe": "vti_iei", "window": "OOS", "verdict": "supports"}]}}}
    got = ro.collect(summary)
    assert got[14]["cells"] == {"IWM": {"IS": "supports"}}
    assert got[23]["cells"] == {"core": {"IS": "contradicts"}}
    assert got[32]["cells"] == {"vti_iei": {"OOS": "supports"}}
    assert ro.collect({"31": {"status": "rejected", "cells": []}})[31]["status"] == "rejected"


def test_synthetic_bil_joins_the_real_fund_and_compounds_the_tbill_rate(monkeypatch):
    days = pd.bdate_range("2007-05-21", "2007-06-05")
    rf = pd.DataFrame({"RF": 0.0002}, index=days)
    monkeypatch.setattr(longdata, "load_french", lambda key: rf)
    launch = pd.Timestamp("2007-05-30")
    head = longdata.synthetic_bil(launch, 69.961)
    assert head.index[-1] < launch and (head["volume"] == 0).all()
    # the launch-day return is the same T-bill rate, so the join is continuous
    assert head["close"].iloc[-1] * 1.0002 == pytest.approx(69.961)
    growth = head["close"].pct_change().dropna()
    assert growth.between(0.000199, 0.000201).all()
