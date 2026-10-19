# Round 18: the five highest-odds ideas from research round 5 (2026-10-18)

Garret asked on 2026-10-17: "Do some deep research to find more ideas. Short and medium. Only the highest chance to pass gets tested but I want at least 5".
Research: `research/deep-research-round5-ranked-ideas-2026-10-18.md` (project folder) ranks ten ideas; the top five are all monthly and are tested here.
No short-horizon idea made the top five (best remaining short idea about 5%; within-industry reversal was already rejected as hypotheses 115-116).
Hypotheses 147-151; 146 were tested before this round.

**This section is written before any result of these tests was computed.**

## Common setup
- Monthly decisions at month-end closes from 2017-01-31, filled at that close, held to the next decision (`round6_scan` engine: `simulate`, `window_stats`).
- Windows: IS 2016-01-01 to 2022-12-31, OOS 2023-01-01 on; minimum 48 / 36 rebalances. Halves of OOS (2023-2024, 2025 on) are reported, not required.
- Costs 5 bps per unit traded (primary), 10 bps (stress).
- **Bar, required in both windows:** net active >= 2.0%/yr vs the benchmark, information ratio >= 0.3, selection placebo >= 0.95 (1,000 random same-size baskets from the ranked names, seed 0), net active > 0 at 10 bps.
- Universe: point-in-time S&P 500 members with a price on the decision day.
- SEC data (share counts, EPS, industry codes) exists only for current members. For tests that need it, the ranked names and the **benchmark are the equal-weight priced members that have a score** that day, so the comparison is like for like.
- Residual momentum is the shadow rule's: `rm.residual_scores(..., **fs.RESMOM6_1)` (6-1 window, three ETF factors).

## Test 1 (hypothesis 147): `resmom6_1_ivw_decile`, residual momentum weighted by steadiness
- Picks: the parent's (top 10% by residual momentum 6-1 among all priced members).
- Weight: proportional to 1 / the standard deviation of the name's daily residuals over the same formation window (the denominator of its score), normalised to sum to 1.
- Benchmark: equal-weight priced members (as the parent).
- Placebo: random baskets of the same size, with the rule's weight vector assigned to the random names in random order.
- **Pass:** the bar in both windows **and** an information ratio above the equal-weight parent's (same run) in both windows.

## Test 2 (hypothesis 148): `nsi_low_quintile`, net share issuance
- Shares now: the latest cover-page share count (`data/round14/shares.csv`) **filed strictly before** the decision day, and filed within the last 120 days.
- Shares a year ago: the latest count filed on or before the decision day minus 365 days, and filed within 120 days before that date.
- Score: minus log(shares now / shares a year ago). Names with |log change| > 0.37 are unscored (splits, reverse splits, very large mergers).
- Hold the 20% with the highest score (biggest fall in shares), equal weight; benchmark equal-weight scored names; at least 20 scored names a day or no trade.
- **Pass:** the bar in both windows.
- Report-only mirror: the 20% with the biggest increase.

## Test 3 (hypothesis 149): `resmom6_1_lowiss_decile`, residual momentum among non-issuers
- Names with both a residual momentum score and an issuance score (test 2).
- Keep names with issuance score at or above the median (shares grew no more than the median). Hold the top 20% of those by residual momentum (about 10% of all ranked names), equal weight.
- Parent in the same run: top 10% by residual momentum among the same names. Benchmark for both: equal-weight names with both scores.
- **Pass:** the bar in both windows **and** net active above the parent's in both windows.

## Test 4 (hypothesis 150): `indmom6_1_quintile`, industry momentum held as stocks
- Industry: two-digit SIC major group (`core.industry.load_sic`).
- Own 6-1 return: close 21 sessions before the decision / close 126 sessions before - 1 (both needed).
- Industry score: equal-weight mean of the own 6-1 returns of the priced members in the group with that return; groups with fewer than 3 such names are unscored.
- Hold the 20% of scored names with the highest industry score, ties broken by own 6-1 return, equal weight. Benchmark equal-weight scored names.
- **Pass:** the bar in both windows.
- Report-only mirror: the 20% with the lowest industry score.

## Test 5 (hypothesis 151): `sue_quintile`, earnings surprise
- EPS: `data/round18/eps.csv` (SEC companyconcept, diluted EPS, basic when no diluted), USD/shares only.
- Quarterly values: facts with a 80 to 100 day period, keeping the **first-filed** value for each period. Fourth quarters: the fiscal-year value (350 to 380 days, first filed) minus the three first-filed quarters ending inside that year; available from the year value's filing date.
- Seasonal change: E(q) - E(q four quarters earlier), the earlier quarter ending 345 to 385 days before.
- SUE: the latest seasonal change / standard deviation of the up-to-8 seasonal changes before it (at least 4, sd > 0).
- The latest quarter must be available strictly before the decision day and within the last 100 days.
- Hold the 20% with the highest SUE, equal weight; benchmark equal-weight scored names; at least 20 scored names a day or no trade.
- **Pass:** the bar in both windows.
- Report-only mirror: the 20% with the lowest SUE.

## Multiple testing
Five rules, all pre-specified above with no variants; mirrors and halves are reported, not judged. A pass would add a candidate to the shadow record only with Garret's say-so.

## Results (run 2026-10-18)

**Verdict: all five rejected (hypotheses 147-151).** Nothing is added to the shadow or paper records. Hypotheses tested after this round: 151.
`backtests/round18_tests/`. Check: the parent residual momentum scores match the shadow rule's to 4e-16, and the parent reproduces its known numbers (IS +4.3%, OOS +8.1%).

Net active per year at 5 bps vs each test's benchmark (IR, placebo); IS = 2017-2022, OOS = 2023 on, a = 2023-2024, b = 2025 on.

| Rule | IS | OOS | OOS a / b | Verdict |
|---|---|---|---|---|
| Parent, residual momentum decile (all names) | +4.3% (0.49, 1.00) | +8.1% (0.66, 1.00) | +1.8% / +15.2% | reference |
| **147** weighted by 1 / residual sd | +3.0% (0.35, 0.99) | +2.0% (0.20, 0.85) | +0.9% / +3.2% | rejected: below parent in both |
| **148** biggest fall in shares | -0.1% (-0.01, 0.47) | +2.5% (0.48, 0.96) | +0.3% / +4.9% | rejected: flat in IS |
| mirror: biggest rise in shares | -0.5% | +3.7% | +2.2% / +5.4% | report only |
| Parent on names with issuance data | +0.6% (0.07, 0.70) | +5.8% (0.45, 1.00) | +0.2% / +12.1% | reference for 149 |
| **149** residual momentum among non-issuers | +1.6% (0.25, 0.86) | +3.1% (0.35, 0.94) | +1.1% / +5.4% | rejected: below bar in IS, below parent in OOS |
| **150** best industries | -0.2% (-0.02, 0.58) | +1.4% (0.13, 0.89) | -0.5% / +3.6% | rejected |
| mirror: worst industries | -0.1% | -1.3% | +0.7% / -3.6% | report only |
| **151** best earnings surprise | -1.6% (-0.33, 0.14) | +4.2% (0.95, 1.00) | +5.7% / +2.6% | rejected: negative in IS |
| mirror: worst earnings surprise | +0.2% | -1.7% | -0.8% / -2.6% | report only |

Coverage: issuance scores for 268 names in 2017 rising to 377; industry 303 to 477 (28 to 39 groups); SUE 266 to 418.

### Plain English
- **Weighting momentum picks toward steadier stocks** made it worse, not better: it shifts money from the names that drive the profit to quieter ones.
- **Buyback stocks** did no better than average from 2017 to 2022. Since 2023 they beat by about 2.5% a year, but stocks that *issued* shares did even better, so this is not the buyback effect; it is the market rewarding a group of growing companies.
- **Momentum among non-issuers** smoothed the 2017-2022 result a little but gave up much of the recent gain, and missed the bar in both windows.
- **Best industries** earned about nothing; the finer industry groups did not rescue the sector-momentum failures we already had.
- **Earnings surprise** is the most interesting miss: strong and steady since 2023 (+4.2% a year, placebo 1.00, and the worst-surprise names lagged) but it lost 1.6% a year from 2017 to 2022. A rule that only works in one era is what we reject; it would need the Sharadar-era data (with full earnings history) to tell whether 2023 on is a new pattern or luck.

### Side finding
The parent momentum rule on only the names that have SEC data (today's members) earned +0.6% a year in 2017-2022, against +4.3% on all names. So in those years much of its edge came from stocks that have since left the index (for example, acquired). Tests limited to today's members are therefore harsher than tests on all names. That does not change any verdict here (148, 150 and 151 were flat or negative in 2017-2022, not just short of the bar), but it is a reason to rerun SEC-based ideas on the Sharadar data, which includes the stocks that left.
