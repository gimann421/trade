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

Run 2026-10-15. Parent rows are `rev5_h3_band40_s` run in the same session (they match round 10/11 exactly).

**Verdict: 1 of the 5 passes: `rev5_h3_band40_vixscale_s` (supported on both the 718 and the 418). The other four are rejected. Hypotheses tested: 125.**

### All 718 names

| Rule | Active share | Net active IS / OOS | IR IS / OOS | At 10 bps IS / OOS | 15:30 price IS / OOS | Turnover IS / OOS | Verdict IS / OOS |
|---|---|---|---|---|---|---|---|
| rev5_h3_band40_s | 1.00 | +7.9% / +4.9% | 0.62 / 0.39 | +4.4% / +1.4% | +7.6% / +5.8% | 71 / 70 | supports/supports |
| rev5_h3_band40_vixgate_s | 0.48 | +6.3% / +3.0% | 0.57 / 0.30 | +3.7% / +0.9% | +6.3% / +2.8% | 53 / 43 | supports/contradicts |
| rev5_h3_band40_vixscale_s | 0.55 | +7.2% / +3.3% | 0.71 / 0.38 | +4.8% / +1.1% | +7.3% / +3.8% | 49 / 44 | supports/supports |
| rev5r_h3_band40_s | 1.00 | +4.8% / +0.7% | 0.42 / 0.06 | +1.4% / -2.7% | +5.8% / +1.3% | 70 / 69 | supports/contradicts |
| rev5v_h3_band40_s | 1.00 | +1.5% / +5.4% | 0.13 / 0.45 | -2.4% / +1.4% | +3.5% / +6.2% | 80 / 81 | contradicts/supports |

### The 418 unseen names

| Rule | Active share | Net active IS / OOS | IR IS / OOS | At 10 bps IS / OOS | 15:30 price IS / OOS | Turnover IS / OOS | Verdict IS / OOS |
|---|---|---|---|---|---|---|---|
| rev5_h3_band40_s | 1.00 | +7.9% / +4.8% | 0.61 / 0.37 | +4.4% / +1.3% | +7.4% / +3.2% | 71 / 71 | supports/supports |
| rev5_h3_band40_vixgate_s | 0.48 | +5.1% / +4.9% | 0.46 / 0.46 | +2.5% / +2.8% | +4.5% / +4.3% | 52 / 43 | supports/supports |
| rev5_h3_band40_vixscale_s | 0.55 | +6.8% / +3.7% | 0.67 / 0.42 | +4.4% / +1.6% | +6.4% / +3.3% | 49 / 44 | supports/supports |
| rev5r_h3_band40_s | 1.00 | +4.0% / +1.3% | 0.34 / 0.12 | +0.5% / -2.2% | +4.7% / +0.9% | 70 / 70 | supports/contradicts |
| rev5v_h3_band40_s | 1.00 | +2.0% / +3.4% | 0.16 / 0.27 | -2.0% / -0.6% | +1.9% / +2.5% | 80 / 81 | contradicts/contradicts |

### Pre-FOMC drift (SPY, previous close to 14:00 on announcement day)

| Window | Events | Gross per event | Net per event (5 bps a trade) | Random same-window mean | Placebo | At 10 bps a trade | Hit rate |
|---|---|---|---|---|---|---|---|
| IS 2017-02-01..2022-12-14 | 48 | 28.0 bps | 18.0 bps | 5.9 bps | 0.939 | 8.0 bps | 56% |
| OOS 2023-02-01..2026-09-16 | 30 | 8.5 bps | -1.5 bps | 8.7 bps | 0.493 | -11.5 bps | 57% |

Verdict: rejected. The 2017-2022 window shows a gross +28 bps per event, but net 18 bps is under the 25 bps bar and the placebo is 0.939 (under 0.95). In 2023 on the drift is gone (gross +8.5 bps, no better than a random morning of +8.7 bps), the pattern the literature reported after 2015.

### What each idea did
- **VIX scale (supported).** Scales the reversal book up when VIX is high and toward the plain market when it is calm (average active share 0.55). Trades less (49 / 44 turns a year against 71 / 70) and gives up some net return (all names +7.2% / +3.3% against the parent's +7.9% / +4.9%), but the information ratio is a little higher over the whole period (0.59 against 0.53) and the break-even cost is a little higher in the earlier window (19.9 against 16.3 bps). It does **not** beat the parent on net return or at 10 bps in the later window (+1.1% against +1.4% on all names), so it passes the bar without being a clear improvement. Gross active is 9.7% / 5.5% on all names.
- **VIX gate (rejected).** Same idea as an on-off switch. Passes every check on the 418 unseen names, but on all 718 the later window's information ratio is 0.2996, a hair under the 0.3 bar. A smooth scale works better than a switch, but this is a near miss, not a clear failure.
- **Residual reversal (rejected).** Removing market beta on top of industry makes it worse than the parent and worse in the later window (+0.7% all, +1.3% unseen); the signal loses what makes it work.
- **Volume filter (rejected).** Dropping names with a volume surge fails the earlier window on both universes (net active +1.5% all, +2.0% unseen) and is below the parent everywhere except the later window on all names.

### Conclusion
Nothing here beats `rev5_h3_band40_s`, but the VIX scale is a second supported rule that trades less and has a slightly better information ratio. Evidence is one well-known conditioning variable tested once, so it needs the shadow record, not conclusions, before any use. Nothing has been added to the shadow or paper records; that waits for Garret. Pre-FOMC drift is gone since 2023.
