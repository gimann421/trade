# Round 12: VIX state, residual reversal, volume filter, pre-FOMC drift (hypotheses 121-125)

- **Date:** 2026-10-15
- **Plan:** round 12 plan written by the coordinator session and approved by Garret on 2026-10-15 ("another run of short horizon ideas"). Order: A (reversal improvements), B (ETF calendar), C (stock event).
- **Ledger hypothesis ids:** 121-125. 120 tested before. Titles "Short-horizon v5: <rule id>" and "Pre-FOMC drift: spy_prefomc".
- **Files:** `strategies/short_horizon_v5.py`, `research/round12_ideas.py`, `research/round12_fomc.py`; VIX from FRED `VIXCLS` (`data/long/fred`), FOMC dates from federalreserve.gov (statement dates, scheduled meetings only), SPY 15-minute bars from Alpaca.
- **What was known:** rounds 1-11. The parent is `rev5_h3_band40_s` (5-day reversal at the 15:45 price, decide every 3 sessions, top 10%, keep a name while it is in the top 40%, fill at the close, 5 bps). It passes the full bar on the 300-name sample, the 418 unseen names and all 718. No return of any rule below has been computed.

## Ideas in the plan that were already tested (skipped, not re-run)
- **A3 intraday-only reversal:** the sum of 5 open-to-close returns is signal `id5`. Rounds 8-9 tested it plain, banded and in quintiles (hypotheses 82-84, 89, 96, 100), all rejected.
- **B5 turn of the month:** hypothesis 11 (days -1..+3), rejected in round 3.
- **B7 month-end rebalancing flow:** hypothesis 32 (60/40 pension tilt on the stock-minus-bond return since last month-end, last 5 sessions), rejected in round 4; hypothesis 31 (Treasury bid) too.
- **C8 earnings-announcement drift:** hypotheses 90-93 (abnormal reaction return in the top 20% or 10% of its own 252-session history, held 5, 20 or 60 sessions), all rejected in round 8. The plan's variant changes only the window (days -1 to +1) and the ranking; I judged that too close to re-run and did not.

## Universe, timing, bar (A rules)
All 718 point-in-time S&P 500 members with 15:45 snapshots, then the 418 outside the round-9 sample. Timing, costs, windows, March 2020 handling and bar exactly as in round 11: net active >= 2%/yr, IR >= 0.3, placebo >= 0.95 in each of 2017-2022 and 2023 on; positive at 10 bps; positive with the 15:30 price in place of 15:45; decisions >= 150 / 100 for hold 3. **Supported only if it passes on both the 718 and the 418.** Each rule is compared with the parent run in the same session.

## Rules (exact)
**A1a. VIX gate, `rev5_h3_band40_vixgate_s`.** At each decision, V is the VIX close of the previous session and M the median of the previous 252 sessions' VIX closes (including that day; FRED holidays forward-filled). If V > M the book is the parent's top-10% book. If V <= M the book is the equal-weight of all priced members (zero active exposure, so the rule is "active only when VIX is high" and costs of switching are paid). The parent's band state (the names it would hold) keeps updating on every decision.
**A1b. VIX scale, `rev5_h3_band40_vixscale_s`.** Same V and M. Active share s = clip(V / M - 0.5, 0, 1) (zero at half the median, full at 1.5 times it). Book = s x the parent's top-10% book + (1 - s) x the equal-weight of all priced members.
**A2. Residual reversal, `rev5r_h3_band40_s`.** Each name's beta to the equal-weight market (mean daily close-to-close return of all loaded names) is estimated over the 60 sessions ending 5 sessions before the decision day (at least 40 observations). Residual 5-day return = (15:45 price over the close 5 sessions earlier, minus 1) minus beta x (mean of that return across all loaded names). The residual is then demeaned within its SIC two-digit group (as in B1 of round 11: groups under 5 ranked names, and names with no code, use the mean of all ranked names). Score = minus the demeaned residual. Differs from round 11's industry-neutral rule by removing market beta first.
**A4. Volume filter, `rev5v_h3_band40_s`.** A name is not ranked if its mean 1:45-to-3:45 volume over the last 5 sessions exceeds 1.5 times the mean of the 60 sessions before them (names without the ratio are not ranked). Differs from round 9's `lv` rules, which kept only names at or below 1.0 times norm and used a plain two-session top decile.

## B6. Pre-FOMC drift, `spy_prefomc` (report: event study, not a universe test)
Hold SPY from the 15:45-bar close (16:00 close) of the session before each scheduled FOMC announcement to the 14:00 price (close of the 13:45 bar) on announcement day; cash otherwise. Scheduled meetings are the statement dates on federalreserve.gov, excluding unscheduled actions (2019-10-11, 2020-03-03, 2020-03-15, 2020-03-23, 2020-03-31, 2025-08-22) and any event in the March 2020 dirty window. Costs 5 bps per trade, two trades per event. Bar, per window (2017-2022 and 2023 on): mean net return per event >= 25 bps (about 2%/yr at 8 meetings a year), placebo >= 0.95 (1000 random draws of as many ordinary sessions, same close-to-14:00 window, seed 0), still positive at 10 bps per trade.

## Reporting rules
Every A rule gets the same table as round 11 plus the parent. A rule is not called a candidate if gross active is under 4%/yr in both windows. The plan's rule that nothing is added to the shadow or paper records until Garret says so applies.

## Limits
The VIX and scale rules mix equal-weight exposure with the top-decile book, so the 5 bps cost includes switching in and out of about 500 names; the placebo for them treats the picks as fully invested. Residual beta uses the loaded names, not an index. The pre-FOMC test has few events (about 8 a year).

## Results
(to be filled after the runs)
