import pandas as pd
import pytest

from core import sharadar as sh


def export(tmp_path):
    rows = [
        # ticker, date, open, high, low, close, volume, closeadj
        ("LEH", "2008-09-12", 4.0, 4.4, 3.8, 4.2, 1000, 4.2),
        ("LEH", "2008-09-15", 3.0, 3.2, 0.1, 0.2, 9000, 0.2),
        ("AAA", "1999-12-31", 20.0, 22.0, 19.0, 20.0, 500, 10.0),   # dividend factor 0.5
        ("AAA", "2016-01-04", 30.0, 31.0, 29.0, 30.0, 500, 15.0),   # after the cut-off
    ]
    path = tmp_path / "sep.csv"
    pd.DataFrame(rows, columns=["ticker", "date", "open", "high", "low", "close", "volume", "closeadj"]).to_csv(path, index=False)
    return path


def test_convert_scales_prices_by_the_dividend_factor_and_cuts_at_2015(tmp_path):
    out = tmp_path / "bars"
    result = sh.convert(export(tmp_path), out, chunksize=2)
    assert result["tickers"] == 2 and result["rows"] == 3
    aaa = pd.read_csv(out / "AAA_1Day.csv", index_col="date", parse_dates=True)
    assert list(aaa.index.strftime("%Y-%m-%d")) == ["1999-12-31"]
    assert aaa.iloc[0]["close"] == pytest.approx(10.0) and aaa.iloc[0]["open"] == pytest.approx(10.0)
    leh = pd.read_csv(out / "LEH_1Day.csv", index_col="date", parse_dates=True)
    assert leh.index[-1] == pd.Timestamp("2008-09-15") and leh.iloc[-1]["close"] == pytest.approx(0.2)


def test_adjust_rejects_an_export_without_the_adjusted_close():
    with pytest.raises(ValueError, match="closeadj"):
        sh.adjust(pd.DataFrame({"ticker": ["A"], "date": ["2000-01-03"], "open": [1], "high": [1], "low": [1],
                                "close": [1], "volume": [1]}))


def test_coverage_needs_a_year_of_history_and_a_bar_near_the_month_end(tmp_path):
    out = tmp_path / "bars"
    out.mkdir()
    for ticker, start, end in [("OLD", "2006-01-03", "2008-09-15"), ("NEW", "2008-06-02", "2008-09-30"),
                               ("GONE", "2006-01-03", "2007-12-31")]:
        days = pd.bdate_range(start, end)
        pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=days.rename("date")).to_csv(
            out / f"{ticker}_1Day.csv")
    membership = pd.Series([frozenset({"OLD", "NEW", "GONE", "MISSING"})], index=pd.DatetimeIndex(["1996-01-02"]))
    table = sh.coverage(membership, out, first="2008-09-30", last="2008-09-30")
    # OLD ended 15 days before month-end, NEW has under a year, GONE ended in 2007, MISSING has no file
    assert table.iloc[0]["members"] == 4 and table.iloc[0]["with_bars"] == 0
    table = sh.coverage(membership, out, first="2008-08-31", last="2008-08-31")
    assert table.iloc[0]["with_bars"] == 1
