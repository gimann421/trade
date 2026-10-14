import numpy as np
import pandas as pd
import pytest

from core import longdata as ld


def yahoo_payload():
    # 2020-03-02 14:30 UTC, 2020-03-03, 2020-03-04 (09:30 New York); the middle bar has no data (holiday-like null)
    ts = [1583159400, 1583245800, 1583332200]
    return {"chart": {"result": [{"timestamp": ts, "indicators": {
        "quote": [{"open": [100.0, None, 110.0], "high": [102.0, None, 112.0], "low": [99.0, None, 108.0],
                   "close": [101.0, None, 111.0], "volume": [1000, None, 1200]}],
        "adjclose": [{"adjclose": [50.5, None, 111.0]}]}}]}}


def test_parse_yahoo_scales_ohlc_by_the_adjustment_factor_and_drops_null_bars():
    frame = ld.parse_yahoo(yahoo_payload())
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert [str(d.date()) for d in frame.index] == ["2020-03-02", "2020-03-04"]
    first = frame.iloc[0]
    assert first["close"] == pytest.approx(50.5)                 # adjclose
    assert first["open"] == pytest.approx(100.0 * 0.5)           # factor = adj / close = 0.5
    assert first["high"] == pytest.approx(51.0) and first["low"] == pytest.approx(49.5)
    assert frame.iloc[1]["close"] == pytest.approx(111.0) and frame.iloc[1]["volume"] == 1200


FRENCH_TEXT = """This file was created by CMPT_IND_RETS_DAILY using the 202608 CRSP database.

  Average Value Weighted Returns -- Daily
,Agric,Food,Soda
19260701,  0.10,  -0.20, -99.99
19260702,  1.00,   2.00,   3.00

  Average Equal Weighted Returns -- Daily
,Agric,Food,Soda
19260701,  0.50,   0.60,   0.70
"""


def test_parse_french_reads_every_table_as_decimals_and_marks_missing():
    tables = ld.parse_french(FRENCH_TEXT)
    assert len(tables) == 2
    vw, ew = tables.values()
    assert list(vw.columns) == ["Agric", "Food", "Soda"]
    assert vw.loc["1926-07-01", "Agric"] == pytest.approx(0.0010)
    assert np.isnan(vw.loc["1926-07-01", "Soda"]) and vw.loc["1926-07-02", "Soda"] == pytest.approx(0.03)
    assert ew.loc["1926-07-01", "Food"] == pytest.approx(0.006)
    assert next(iter(tables)).startswith("Average Value Weighted Returns -- Daily")


def test_parse_fred_handles_missing_markers():
    text = "observation_date,DGS10\n2020-01-01,.\n2020-01-02,1.88\n2020-01-03,1.80\n"
    s = ld.parse_fred(text, "DGS10")
    assert list(s.index) == list(pd.to_datetime(["2020-01-02", "2020-01-03"])) and s.iloc[0] == pytest.approx(1.88)
    assert s.name == "DGS10"
