import pandas as pd
import pytest

from core.universe import last_member_dates, load_membership, members_on, month_end_members


@pytest.fixture
def membership(tmp_path):
    path = tmp_path / "members.csv"
    path.write_text(
        "date,tickers\n"
        '2016-11-15,"AAA,BBB,FB"\n'
        '2017-01-10,"AAA,BBB,CCC,FB"\n'   # CCC added
        '2017-02-20,"AAA,CCC,FB"\n'       # BBB removed mid-month
        '2017-03-08,"AAA,CCC,META"\n'     # FB renamed META
    )
    return load_membership(path)


def test_members_on_uses_latest_row_on_or_before(membership):
    got = members_on(membership, ["2016-12-30", "2017-01-10", "2017-02-28", "2017-06-30"])
    assert got == [{"AAA", "BBB", "FB"}, {"AAA", "BBB", "CCC", "FB"}, {"AAA", "CCC", "FB"}, {"AAA", "CCC", "META"}]
    with pytest.raises(ValueError):
        members_on(membership, ["2016-01-01"])


def test_month_end_members_and_asof_dates(membership):
    assert month_end_members(membership, "2016-12-31", "2017-03-31") == {"AAA", "BBB", "CCC", "FB", "META"}
    last = last_member_dates(membership, "2016-12-31", "2017-03-31")
    # BBB was last listed on the 2017-01-10 row; FB on the 2017-02-20 row
    assert last["BBB"] == pd.Timestamp("2017-01-10")
    assert last["FB"] == pd.Timestamp("2017-02-20")
    assert last["META"] == pd.Timestamp("2017-03-08")
    # a ticker only listed before the window is not wanted
    assert month_end_members(membership, "2017-03-31", "2017-03-31") == {"AAA", "CCC", "META"}
