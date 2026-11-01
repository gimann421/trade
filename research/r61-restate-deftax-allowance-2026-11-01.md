# Round 61: re-reported comparatives, deferred tax expense and bad-debt reserve build (2026-11-01)

Garret asked (2026-11-01) for an Opus idea pass with this thread running the tests. The ranked list is `/mnt/project-files/research/opus-new-ideas-ranked-2026-11-01.md` (twelve ideas, run in the listed order, one rule each, no variants). This round runs ideas 1 to 3 as hypotheses 270 to 272. 269 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of this test was computed.** No return of any of these rules was looked at before writing it.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 270 `revisionrate_quintile`: for each 10-K, take every us-gaap USD fact from companyfacts whose period is the prior fiscal year (annual durations of 350-380 days ending 335-395 days before the 10-K's own fiscal year end, and instants at that prior year end). Match each to the same tag and period as first filed in an earlier 10-K. Revision rate = share of matched facts whose value changed by more than 0.5% of the original (an original of 0 that becomes non-zero counts as changed). At least 30 matched facts. Hold the lowest 20%.
- 271 `lowdeftax_quintile`: `DeferredIncomeTaxExpenseBenefit` (fallback `DeferredIncomeTaxesAndTaxCredits`) / assets, latest fiscal year, first-filed 10-K values. Hold the lowest 20% (most negative). Reported, not judged: the result excluding 2-digit SIC 60 to 67.
- 272 `allowancebuild_quintile`: R = allowance / (net receivables + allowance), allowance from `AccountsReceivableAllowanceForCreditLossCurrent` if reported that year, else `AllowanceForDoubtfulAccountsReceivableCurrent`; net receivables `AccountsReceivableNetCurrent`. Score = R this fiscal year minus R the year before (R last year > 0). Exclude 2-digit SIC 60 to 67. Hold the highest 20%.
Annual data: latest 10-K filed before the decision, fiscal year ending within the last 455 days.

## Common setup
Round 25-60 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes; tech/health share. Correlation above 0.7 with an existing pass is the same bet.

## Multiple testing
Three rules, no variants. Total tested after this round: 272.

## Caveats stated in advance
New accounting standards (ASC 606 in 2018, ASC 842 in 2019) push many firms' revision rates up in the same year; the cross-sectional rank absorbs most of that. The CECL tag switch in 2020-21 can move R for reasons other than judgment (disclosed, not corrected).

## Results (run 2026-11-01)

**Verdict: all three rejected (hypotheses 270-272).** Tests after this round: 272. `backtests/round61_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage: 316-493 scored names (270), 216-431 (271), 98-184 (272).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 270 lowest comparative revision rate | +0.4% (IR 0.15, pl 0.70) | -2.8% (-0.95, pl 0.03) | rejected |
| 271 lowest deferred tax expense / assets | +0.6% (0.13, pl 0.70) | +4.3% (0.81, pl 1.00) | rejected: nothing in-sample |
| 272 largest allowance build | -0.3% (-0.05, pl 0.44) | -1.2% (-0.24, pl 0.38) | rejected |

Reported, not judged:
- 271 excluding SIC 60-67: IS +0.5% (pl 0.62), OOS +5.3% (IR 0.98, pl 1.00). Same split, so no rescue from dropping financials.
- Mirrors: highest revision rate IS +2.6% (IR 0.94, pl 1.00) but OOS +1.1% (pl 0.78); highest deferred tax IS -2.7%; smallest allowance build IS -1.2%, OOS -2.7%. None meets the bar.
- Correlation with the three passes: deferred tax 0.36 (low accruals), -0.33 (sales/price), 0.60 (R&D; 61% tech/health picks); revision rate and allowance build at most 0.44 in absolute terms. Nothing above 0.7.

Data note, disclosed after the fact: the tag `AccountsReceivableAllowanceForCreditLossCurrent` returned 404 for all 503 members from companyconcept, so rule 272 ran on the pre-registered fallback tag `AllowanceForDoubtfulAccountsReceivableCurrent` alone (340 members; 98-184 scored names a month). The CECL tag switch noted in advance therefore does not affect it, but names that only use the newer concept after 2020 are unscored. Revisions were computed from companyfacts first-filed annual 10-K values (6,970 filing rows, 498 members).

### Plain English
Companies whose past numbers rarely get re-reported, companies with low deferred taxes, and companies building up their bad-debt reserve did not beat the average. Low deferred taxes did well since 2023 but nothing before, so it is not a steady effect. No pass.
