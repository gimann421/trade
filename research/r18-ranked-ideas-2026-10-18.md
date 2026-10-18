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
