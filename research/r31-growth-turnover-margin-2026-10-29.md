# Round 31: sales growth, asset turnover, margin change and earnings growth (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 199-202; 198 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged. These four use SEC data already downloaded (net income, assets, revenue), so nothing new is fetched.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
- **Low sales growth** (Lakonishok-Shleifer-Vishny 1994 "contrarian investment", glamour versus value): firms with the slowest sales growth earn more than high-growth "glamour" firms. Direction pre-fixed: lowest revenue growth year over year.
- **High asset turnover** (Soliman 2008; Novy-Marx 2013 splits profitability into margin and turnover): revenue over assets, highest quintile.
- **Rising net margin** (Piotroski 2000; Soliman 2008 DuPont changes): the year-over-year rise in net income over revenue, highest quintile.
- **High earnings growth** (Chan-Jegadeesh-Lakonishok 1996 earnings momentum components): net income growth over the prior year's net income, among names with positive net income in both years.

## Common setup
Round 25-30 setup exactly (annual first-filed 10-K values usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names). Revenue is Revenues if reported, else RevenueFromContractWithCustomerExcludingAssessedTax (round 27 definition). Prior year = fiscal year end 335-395 days earlier; prior revenue must be above 0.
- 199 `lowsalesgrowth_quintile`: lowest revenue / prior revenue - 1.
- 200 `turnover_quintile`: highest revenue / assets.
- 201 `marginchange_quintile`: highest (net income / revenue) minus the prior year's (revenue above 0 in both years).
- 202 `earningsgrowth_quintile`: highest net income / prior net income - 1, both net incomes above 0.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation of the monthly active return with low accruals and with R&D intensity (above 0.7 means the same bet, not a new rule); the tech/health share of the picks.

## Multiple testing
Four rules, no variants. Total tested after this round: 202.

## Results (run 2026-10-29)

**Verdict: all four rejected (hypotheses 199-202).** Tests after this round: 202. `backtests/round31_tests/`. Check: the low-accruals and R&D references reproduce (IS +2.8% / +5.5%, OOS +3.2% / +15.8%).

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 199 lowest sales growth | +0.9% (0.14, 0.73) | -0.1% (-0.02, 0.46) | rejected: no edge |
| 200 highest revenue / assets | +3.4% (0.69, 1.00) | -2.9% (-0.62, 0.03) | rejected: reversed since 2023 |
| 201 largest rise in net margin | -1.7% (-0.33, 0.08) | +3.8% (0.65, 0.99) | rejected: one era only |
| 202 highest earnings growth | -1.5% (-0.31, 0.10) | +3.6% (0.69, 0.99) | rejected: one era only |

Mirrors (report only): highest sales growth +1.1% / +4.0%; lowest turnover -4.7% / -2.4%; falling margin -1.5% / -0.6%; lowest earnings growth +0.1% / -2.1%. Correlation with low accruals: 0.10, -0.17, 0.10, 0.08. Correlation with R&D intensity: -0.40, -0.06, 0.37, 0.41. Mean tech/health share of picks: 36%, 26%, 42%, 40%.

### Plain English
- **Slow sales growth** (the old "contrarian" idea) showed no edge in either period.
- **Companies that squeeze the most revenue from their assets** beat the average in 2017-22 and lagged since 2023, so it did not last.
- **Improving profit margins** and **fast earnings growth** each did nothing in 2017-22 and well since 2023: one period only, which fails.
- No new rule. Low accruals and R&D intensity remain the only two. Growth-style numbers (sales, earnings, margins) have now failed in every form tried, which fits the pattern that only "quality of earnings" and "investment in intangibles" held up.
