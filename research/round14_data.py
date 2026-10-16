"""Shares outstanding (SEC cover-page counts) and macro-announcement dates for round 14.

    PYTHONPATH=. python research/round14_data.py shares      # data/round14/shares.csv: ticker, filed, shares
    PYTHONPATH=. python research/round14_data.py dates       # data/round14/announcements.csv: date, kind

Shares: data.sec.gov companyconcept dei/EntityCommonStockSharesOutstanding for each CIK of the current S&P 500
(the same constituent file core/edgar.py uses). A count is usable from its filing date on. Names with several share
classes report the count per class (dimensional facts, not in this feed) and are left out; so are names that have
left the index (no CIK). They are never ranked by turnover.
Dates: FOMC statement days from the Federal Reserve calendar pages; employment-report days from the BLS rule
(third Friday after the end of the reference week that contains the 12th) with the shifts listed in SHIFTS. CPI is left out: no free source of its release dates was reachable.
"""

import json
import sys
import time
import urllib.request

import pandas as pd

from core.data import DATA_DIR
from core.edgar import HEADERS, load_constituents

OUT = DATA_DIR / "round14"
CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/dei/EntityCommonStockSharesOutstanding.json"


def fetch_shares() -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, missing = [], []
    for n, (symbol, cik) in enumerate(sorted(load_constituents().items()), 1):
        try:
            req = urllib.request.Request(CONCEPT.format(cik=cik), headers=HEADERS)
            payload = json.loads(urllib.request.urlopen(req, timeout=60).read())
            for r in payload["units"]["shares"]:
                rows.append({"symbol": symbol, "cik": cik, "end": r["end"], "filed": r["filed"], "form": r.get("form"),
                             "shares": r["val"]})
        except Exception as exc:
            missing.append((symbol, f"{type(exc).__name__}: {str(exc)[:60]}"))
        time.sleep(0.12)
        if n % 100 == 0:
            print(n, len(rows), len(missing), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "shares.csv", index=False)
    (OUT / "shares_missing.json").write_text(json.dumps(missing, indent=1))
    print(f"{frame.symbol.nunique()} symbols with counts, {len(missing)} without")
    return frame


def load_shares() -> pd.DataFrame:
    frame = pd.read_csv(OUT / "shares.csv", parse_dates=["filed", "end"])
    return frame.sort_values(["symbol", "filed"])


# --- announcement dates ---------------------------------------------------------------------------------------

# Last day (statement day) of each scheduled FOMC meeting, from the Federal Reserve calendar pages; 2020-03-16 is the
# first session after the emergency decision of Sunday 15 March. The 2021, 2022, 2024 and 2026 rows were checked
# against the calendar page text by script.
FOMC = """2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-03-16 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17""".split()

# BLS employment report: third Friday after the end of the reference week (the Sunday-Saturday week with the 12th).
# Known shifts: a rule date of January 3 moved to January 10 (reports for December 2019 and December 2024), and the
# June 2020 report came out Thursday 2 July (the 3rd was the holiday). The window stops at 2025-09-30: the autumn-2025
# shutdown moved the schedule.
SHIFTS = {pd.Timestamp("2020-01-03"): pd.Timestamp("2020-01-10"), pd.Timestamp("2025-01-03"): pd.Timestamp("2025-01-10"),
          pd.Timestamp("2020-07-03"): pd.Timestamp("2020-07-02")}


def employment_dates(start="2016-01-01", end="2025-09-30") -> list:
    out = []
    for month in pd.period_range(start, end, freq="M"):
        twelfth = month.to_timestamp() + pd.Timedelta(days=11)
        reference_saturday = twelfth + pd.Timedelta(days=(5 - twelfth.weekday()) % 7)
        friday = reference_saturday - pd.Timedelta(days=1) + pd.Timedelta(weeks=3)
        friday = SHIFTS.get(friday, friday)
        if pd.Timestamp(start) <= friday <= pd.Timestamp(end):
            out.append(friday)
    return sorted(set(out))


def fomc_dates() -> list:
    return [pd.Timestamp(d) for d in FOMC]


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "shares":
        fetch_shares()
    elif what == "dates":
        OUT.mkdir(parents=True, exist_ok=True)
        fomc, emp = fomc_dates(), employment_dates()
        rows = [(d, "fomc") for d in fomc] + [(d, "employment") for d in emp]
        pd.DataFrame(rows, columns=["date", "kind"]).sort_values("date").to_csv(OUT / "announcements.csv", index=False)
        print(len(fomc), "FOMC days", len(emp), "employment days")
