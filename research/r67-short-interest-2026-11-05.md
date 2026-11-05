# Round 67: short interest (2026-11-05)

First round of the second Opus idea list (`/mnt/project-files/research/opus-new-ideas-round2-ranked-2026-11-05.md`, requested by Garret 2026-11-05 as "more research"): ideas 1, 2 and 6, which share one FINRA pull, as hypotheses 282, 283 and 284 (numbered in registration order; the other ideas continue from 285). 281 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of these tests was computed.** No return of any rule was looked at before writing it.

## Data and shortened in-sample window (stated before the run)
FINRA consolidated short interest, per current member, twice a month, history from 2018-07-13 (api.finra.org). The first usable value is on 2018-07-31, so the **in-sample window is 2018-07 to 2022-12, about 54 monthly decisions instead of 72**; this still clears the 48-rebalance minimum in the bar, and out-of-sample (2023 on) is unchanged. Two members (BF.B, BRK.B) are unknown to FINRA and are left out. A value is usable only 12 calendar days after its settlement date (FINRA publishes about 7 business days after settlement; the idea list said 8 days, which could look ahead, so the later date is used). Shares outstanding: latest `EntityCommonStockSharesOutstanding` (round 36 file) filed before the decision day and within 400 days; for multi-class companies this cover-page figure may cover one class only, which adds noise and is not corrected.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 282 `lowshort_quintile`: ratio = latest published short position / shares outstanding, settlement within 45 days before the decision day. Hold the lowest 20%.
- 283 `shortdrop_quintile`: (short position now - short position at the settlement date closest to 182 days earlier, within 10 days of that) / shares outstanding. Hold the 20% with the largest fall.
- 284 `lowacc_lowshort`: take the 40% of accrual-scored names with the lowest accruals (the low accruals pass's score), keep those with a ratio as in 282, and hold the 20% of that group with the lowest ratio. Benchmark and placebo universe: that same low-accrual group. At least 20 names in the group. A test of the short-interest filter on top of the low accruals pass, not of accruals again.

## Common setup
Round 25-66 setup exactly (current S&P 500 members, monthly decisions, 5/10 bps, OOS 2023+, minimum 20 scored names) except decisions start 2018-07-31 for every rule here, including the three reference passes.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps, at least 48 / 36 rebalances. Reported, not judged: mirrors; correlation with the three passes (key for 282 and 284); tech/health share. Correlation above 0.7 with an existing pass means the same bet. 282 and 284 are well-published effects and must show they still work.

## Multiple testing
Three rules, no variants. Total tested after this round: 284.

## Results (run 2026-11-05)

**Verdict: all three rejected (hypotheses 282-284).** Tests after this round: 284. `backtests/round67_tests/`. FINRA data for 501 of 503 members; 313-440 names scored (282), 326-436 (283), low-accrual group of 82-143 names (284). In-sample is 2018-07 to 2022-12 (53 rebalances, as stated up front). Reference rules over the same window: low accruals +3.1/+3.2, R&D +5.6/+15.8, sales/price +4.9/+3.3.

| Rule | IS 2018-22 | OOS 2023+ | Verdict |
|---|---|---|---|
| 282 least shorted | -0.9% (IR -0.17, pl 0.29) | -1.9% (IR -0.40, pl 0.13) | rejected: wrong sign |
| 283 shorts giving up most | +0.7% (0.17, pl 0.83) | +1.5% (0.36, pl 0.92) | rejected: below the bar |
| 284 low accruals and least shorted | -1.5% (-0.17, pl 0.27) | -2.4% (-0.31, pl 0.23) | rejected: filter hurts |

Reported, not judged:
- **Post hoc lead (not counted, found after looking): the MOST shorted fifth** (the mirror of 282) gave IS +2.6% (IR 0.43, pl 0.98, 10 bps +2.4%) and OOS +3.8% (IR 0.60, pl 1.00, 10 bps +3.6%), which would clear every line of the bar. It was not the pre-registered direction, so by the standing rule it cannot be confirmed in this window; it needs a later or independent window (more months of forward data, or a pre-2018 era if FINRA history or Sharadar becomes available). Correlation of 282 with low accruals -0.25, R&D -0.05, sales/price -0.39 (so the mirror is not a copy of any pass). Tech/health share 46%. A heavily shorted large-cap fifth beating the rest is the opposite of the published sign, consistent with a squeeze-prone or high-beta recent-era effect; it was not checked for a beta or momentum tilt.
- 283 mirror (shorts piling in) IS -0.1%, OOS -1.4%.

### Plain English
Stocks few people bet against did worse than average in both periods, not better, so the idea that "nobody doubts it" is a good sign did not hold. Stocks where short sellers were giving up gained a little but not enough, and adding the short filter to the low accruals idea made it worse. The one interesting thing is the reverse: the most shorted fifth of stocks did well in both periods. We only noticed that after looking, so it is a lead to watch, not a result.
