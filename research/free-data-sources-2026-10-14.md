# Free long-history data (2026-10-14)

What was pulled, what it covers, and what the cross-check against Alpaca found. Code: `core/longdata.py`; files land in `data/long/` (gitignored). Rebuild with `python -m core.longdata all`.

## What is there
| Source | Files | Coverage | Notes |
|---|---|---|---|
| Yahoo daily bars (unofficial chart endpoint) | 36 ETFs, `data/long/<SYM>_1Day.csv` | SPY from 1993-01; nine sector funds from 1998-12; QQQ 1999-03; IWB/IWD/IWF/IWM 2000-05; VTI 2001-06; EFA 2001-08; IEF/LQD/SHY/TLT 2002-07; EEM 2003-04; AGG 2003-09; VNQ 2004-09; GLD 2004-11; DBC 2006-02; IEI/TLH 2007-01; HYG 2007-04; BIL/SPTL 2007-05; VEA 2007-07; EDV 2008-01; ZROZ 2009-11; VGIT 2009-11; VGLT 2010-01. All run to 2026-10-12 | Open, high, low and close are scaled by the dividend adjustment so they match Alpaca's layout. ETFs only: Yahoo has nothing for delisted stocks, and a reused ticker returns a different company |
| Ken French library | `data/long/french/`: Fama-French 3 and 5 factors, momentum, short-term reversal, 49 industries (value- and equal-weighted), all daily | 1926 to 2026-08-31 (5 factors from 1963) | Built from CRSP including delisted stocks, so no survivorship bias; portfolios, not tradable funds |
| FRED | `data/long/fred/`: DGS10, DGS2, DGS3MO, DTB3, DFF, T10Y2Y, BAA10Y, BAMLH0A0HYM2, VIXCLS | DTB3 from 1954, DGS10 1962, DGS2 1976, DGS3MO 1981, BAA10Y 1986, VIXCLS 1990; BAMLH0A0HYM2 only from 2023-10 (licence limit) | Rates and spreads, no prices |

Not reachable from this environment: Stooq. Not usable: any free source of delisted-stock prices. Yahoo returned nothing for 44 of 50 well-known delisted names and the wrong company (a reused ticker) for the other six; Alpaca has no daily bars before 2016; Alpha Vantage rejected Lehman.

## Yahoo against Alpaca, 2016 to 2026, 36 ETFs
- Volumes agree within about 1%, so Alpaca's daily bars are consolidated, not IEX-only.
- Typical close-to-close return gap, for example XLE: median 1.1 bps, 90th percentile 4.5 bps. Cumulative ten-year growth agrees within 1% for 33 of 36 funds; the exceptions are XLF (+19.7%, see below), EDV (+2.3%) and DBC (-1.3%).
- **69 of 97,480 fund-days (0.07%) differ by more than 1 percentage point; 64 of the 69 fall in March 2020.** The two sources move in opposite directions on consecutive days, so the error reverses the next day. Example, SPY on 2020-03-13: Yahoo +8.55%, Alpaca +5.86%. The S&P 500 rose about 9.3% that day (from memory, not looked up), which fits Yahoo. Alpaca's close for the extreme days of March 2020 looks like a late-session print rather than the official close.
- **XLF has a false -17.8% day in Alpaca on 2016-09-19.** That is the day the real estate sector was carved out of the financials index; Yahoo treats it as a distribution and keeps the return continuous (+0.6%), Alpaca does not adjust it, so XLF's growth over the ten years differs by +19.7% between the two. Any earlier result that used XLF (the overnight rules H26-H28) saw that drop. Other funds show smaller one-offs (XLB in July 2018, DBC on 2018-12-26).
- No re-scoring was done. What this means for earlier results is not yet known; the March 2020 errors reverse the next day, so multi-day holds are barely touched, but one-day signals were exposed.

## How these files will be used
- The older-era ETF retest (next step) uses Yahoo files only for 1998-2015, so there is no stitching of two sources.
- Alpaca's stock bars (719 members) were not cross-checked: Yahoo cannot serve delisted names.
