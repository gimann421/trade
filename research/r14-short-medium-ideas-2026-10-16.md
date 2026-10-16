# Round 14: ideas from the second deep-research report (2026-10-16)

Source of the ideas: `research/deep-research-short-medium-horizon-round2-2026-10-15.md` (stored in the project folder;
Garret asked for the recommended order on 2026-10-16: 3:45 fills first, then the two momentum branches together,
then announcement days). Hypotheses 134-138; 133 were tested before this round.

**This section is written before any result of these rules was computed.**

## Common set-up
- Universe and data as in earlier rounds: point-in-time S&P 500 members, Alpaca daily bars, adjusted; 3:30 and 3:45
  snapshots (`core/intraday.py`) for the fixed random sample of 300 names (test 1 only). Costs 5 bps per unit of
  turnover unless a test says otherwise. Windows: IS = 2016-2022, OOS = 2023 on (decisions start 2016-12-30 for the
  daily rules and 2017-01-31 for the monthly rules). The data were downloaded afresh in this session, so counts can
  differ a little from the earlier memos.
- Every rule is compared with its parent run in the same session on the same data.

## Test 1: fill the reversal rules at 3:45 instead of at the close (hypotheses 134, 135)
Parents: `rev5_h2_band_s` and `rev5_h3_band40_s` (decision at the 3:45 price, fill at the official close).
New rules `rev5_h2_band_f45_s` and `rev5_h3_band40_f45_s`: the **signal is read at the 3:30 price** (the 5-day return to
3:30, rank and band as in the parent), and the orders are filled at the **3:45 price**, which is the only way to act on
a signal in practice (the order has to be sent after the snapshot). Holdings are valued at the 3:45 price on every
later day, so a position earns 3:45-to-3:45 returns; the equal-weight benchmark is built and costed the same way.
- **Cost of the 3:45 fill:** 5 bps plus 2 bps for crossing the spread, so **7 bps per unit of turnover** (the closing
  auction is assumed to cost 5 bps as before). Also reported at 5, 9 and 11 bps.
- **Control (the comparison that isolates the fill time):** the same 3:30 signal filled at the official close, 5 bps
  (the `noisy` variant of round 9). The effect of the fill time is: net active of the 3:45 rule minus net active of the
  control. Report-only upper bound: the 3:45 signal filled at 3:45 (not executable).
- **Bar for "supported":** in both windows (a) the 3:45-fill rule beats its control by **>= 1.0%/yr** net active at
  7 bps, (b) the 3:45-fill rule's own net active vs its benchmark is above 0, and (c) a block bootstrap (21-day blocks,
  1,000 draws, seed 0) of the daily difference gives P(difference > 0) >= 0.80. Decision days must number at least 250
  (IS) and 150 (OOS) for the 2-day rule and 160 / 100 for the 3-day rule.
- Limits known in advance: 300 sampled names (about 210 members on any date); the snapshot has only 3:30 and 3:45, so at
  most the last 15 minutes of the end-of-day pattern can be captured; the paper's sample ends in 2019.

## Test 2: short-term momentum for heavily traded names, in the momentum rule (hypothesis 136)
Parent: `stock_resmom6_1_decile` (monthly, top decile by residual momentum, formation window t-126..t-21, min 105 valid
days, as in `research/round6_scan.py`). New rule `resmom_sttm_decile`: score = z(res6) + 0.5 x z(res1) x H, where res6
is the parent score, res1 is the same residual (betas from the formation window) mean over its standard deviation on
sessions t-20..t, z is the cross-sectional z-score among that month's ranked names, and H = 1 for names whose
prior-month turnover (sum of volume over the last 21 sessions divided by the latest SEC cover-page share count filed
by then) is in the top 30% of names with a count, else 0. Names without a share count are not high turnover (score =
parent). Share counts exist for current index members with one share class; names that have left the index, and
multi-class names, therefore keep the parent score (a survivorship limit, and the reason for the parent comparison).
Top decile, equal weight, monthly, 5 bps.

## Test 3: announcement days (hypothesis 138)
Rule `announce_spy_s`: hold SPY from the close before each FOMC statement day and each employment-report day to the
close of that day (about 20 days a year), BIL otherwise; 1 bp per side. Employment-report days follow the BLS rule with
three documented shifts (`research/round14_data.py`); the window stops at 2025-09-30 (the autumn-2025 shutdown moved the
schedule). **CPI is left out: no free source of its release dates was reachable from this environment**, so this
tests two of the three announcement types.
- **Bar for "supported":** in both windows (IS 2016-2022, OOS 2023 to 2025-09-30), the mean SPY return in excess of BIL on
  announcement days net of costs is >= 8 bps per day, with a t-statistic >= 1.65 (day-level, no clustering needed
  because the days are far apart), and it exceeds the mean excess return of all other days by >= 6 bps.
- Placebo: the percentile of the announcement-day mean among 1,000 random sets of the same number of days in the same
  window (seed 0); must be >= 0.95.

## Test 4: frog-in-the-pan filter on residual momentum (hypothesis 137)
Parent as in test 2. New rule `resmom_fip_decile`: take the 30% of ranked names with the highest res6; among them hold
the third with the lowest FIP, where FIP = sign(cumulative residual return over the formation window) x (share of
formation days with a negative residual return minus share with a positive one); a lower FIP means the gain came in many
small steps. The book therefore has the same size as the decile. Equal weight, monthly, 5 bps.

## Bar for tests 2 and 4
The scan bar of `research/r6-factor-scan-2026-10-13.md`: net active vs the equal-weight members >= 2.0%/yr, information
ratio >= 0.3, selection placebo >= 0.95, in both windows, with at least 48 / 36 rebalances; **and** net active above the
parent's in both windows (a branch must improve on its parent, as in round 13).

## Results
(to be added)
