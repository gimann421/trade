# Round 63: order backlog growth, no SEC comment letters, earnings smoothing (2026-11-02)

Third round of the Opus idea list (`/mnt/project-files/research/opus-new-ideas-ranked-2026-11-01.md`, requested by Garret 2026-11-01): ideas 7, 11 and 12 as hypotheses 275, 276 and 277. 274 were tested before this round, so a lucky pass is more likely than for a single test. Ideas 6, 8, 9 and 10 stay on hold: they need SEC bulk downloads from www.sec.gov, which return 403 here because SEC_CONTACT is not set. Bar unchanged from round 25.

**This section is written before any result of these tests was computed.** No return of any of these rules was looked at before writing it.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names; 276 is a basket)
- 275 `rpogrowth_quintile` (idea 7): `RevenueRemainingPerformanceObligation` (USD, no dimension) from the latest 10-Q or 10-K filed before the decision and within the 150 days before it; prior = the same instant fact whose period end is 335 to 395 days before the current period end (first-filed value). Score = (RPO now - RPO a year earlier) / revenue of the latest 10-K filed before the decision (first-filed full-year value of `RevenueFromContractWithCustomerExcludingAssessedTax`, else `Revenues`; revenue must be > 0). Hold the highest 20%. **In-sample length stated up front:** RPO exists from ASC 606 (fiscal 2018), so the first scored decisions come around mid-2019 and the in-sample window holds about 43 months, short of the usual 48. The in-sample figure is judged as it stands, and a pass would still be flagged as resting on a short window. Coverage about 45% of members.
- 276 `nocommentletter_basket` (idea 11): SEC staff letters are EDGAR filings of form UPLOAD (data.sec.gov submissions, current members, history from 2014-01). Whether the listed filing date is the public release date could not be confirmed on five threads: the letter documents on www.sec.gov return 403 here. The pre-registered fallback applies: a letter becomes public on its filing date plus 120 days. A member is scored on a decision date only if its submissions history reaches back at least 850 days before the date. Basket = all scored members with no letter whose public date falls in the 730 days up to the decision. Equal weight vs the equal-weight scored members. No quintile; a basket holds about half the index.
- 277 `lowsmoothing_quintile` (idea 12): over the latest 5 usable fiscal years (at least 4; first-filed 10-K values of net income, operating cash flow, assets; year usable once its 10-K is filed; latest year's end within 455 days), score = std(net income / assets) divided by std(operating cash flow / assets); cash-flow std must be > 0. Hold the highest 20% (least smoothing).

## Common setup
Round 25-62 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes (277 is the closest relative of low accruals and of the rejected 273); tech/health share. Correlation above 0.7 with an existing pass means the same bet. The memo's expectation for 276 is low: avoidance rules holding half the index came in near zero in round 48.

## Multiple testing
Three rules, no variants. Total tested after this round: 277.

## Results (run 2026-11-02)

**Verdict: all three rejected (hypotheses 275-277).** Tests after this round: 277. `backtests/round63_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage: 275 scored 70-120 names from mid-2019 (none before; only 44 in-sample months, as stated up front), 276 323-497, 277 165-395.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 275 fastest-growing order backlog | +0.5% (IR 0.07, pl 0.59) | +7.9% (IR 0.96, pl 1.00) | rejected: nothing in-sample, only 44 months |
| 276 no comment letters | -0.2% (IR -0.11, pl 0.36) | +0.8% (IR 0.66, pl 0.92) | rejected: near zero both windows |
| 277 least earnings smoothing | +0.8% (IR 0.22, pl 0.76) | +0.2% (IR 0.06, pl 0.56) | rejected: near zero both windows |

Reported, not judged:
- 275 mirror (slowest backlog growth) IS -3.3%, OOS -5.6%. Picks are 78% tech/health; correlation with sales/price -0.51, R&D 0.39, low accruals 0.11. The OOS strength with a flat in-sample is the pattern of a recent tech tilt, not a lead (post hoc anyway).
- 276 mirror (members with letters) IS +0.4%, OOS -0.9%.
- 277 mirror (most smoothing) IS +0.1%, OOS -1.9%. Correlation of 277 with low accruals 0.24.
- Comment-letter release dates could not be confirmed (letter documents on www.sec.gov return 403 here), so the pre-registered filing date + 120 days applied.

### Plain English
Companies with fast-growing order backlogs did great from 2023 but did nothing before it, and the data only reaches back to mid-2019, so it is not a pass. Having no SEC comment letters, or reporting profits that track cash closely, made no difference either way. No pass.
