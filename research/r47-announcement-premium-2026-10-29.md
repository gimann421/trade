# Round 47: earnings announcement premium (2026-10-29)

Garret's standing ask (keep searching until more rules pass; relayed by the coordinator 2026-10-29). Idea chosen by the thread. Hypothesis 240; 239 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the number of earnings-release 8-Ks per year and their dates for one ticker were looked at.

## Where the idea comes from
The earnings announcement premium (Frazzini-Lamont 2007, "The earnings announcement premium and trading volume"; Savor-Wilson 2016): stocks earn abnormally high returns in the months in which they are expected to announce earnings, because announcements are predictable high-attention events. Round 3 looked at the idea only at index level with sector ETFs and found nothing; the stock-level version with actual release dates was never tested. The release dates come from the round 44 SEC submissions download: 8-K filings carrying item 2.02 (results of operations and financial condition) are the earnings releases, 22,339 of them for 503 current members from 2015-10 on.

## Rule
- 240 `annpremium_quintile` (name kept for the harness; the portfolio is not a quintile): at each month-end decision, hold every scored name that is predicted to announce in the next 30 calendar days, meaning at least one of its item 2.02 8-Ks was filed in the same window one year earlier (decision day + 1 to + 30 days, minus 365 days). Equal weight. Benchmark: equal-weight all scored names (a name is scored if it has at least 6 item 2.02 8-Ks in the file). Direction: announcers. The mirror (names not predicted to announce) is reported, not judged. About a third of names are expected to be picked each month.

## Common setup
Round 25-46 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names. The harness's placebo compares against random portfolios of the same size.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirror; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks.

## Multiple testing
One rule, no variants. Total tested after this round: 240.

## Results (run 2026-10-30)

**Verdict: rejected (hypothesis 240); the sign is right in both windows but the size is below the bar and costs remove it.** Tests after this round: 240. `backtests/round47_tests/`. Check: the low-accruals, R&D and sales/price references reproduce. Coverage 338 to 497 scored names per month; about a third are picked each month.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 240 names predicted to announce next month | +0.4% (0.10, 0.92) | +1.1% (0.22, 0.93) | rejected: below 2.0% and IR 0.3, placebo below 0.95, and net active is negative at 10 bps (-0.7% / -0.0%) |

Mirror (names not predicted to announce, report only): -0.9% / -1.7% (IR -0.63 / -1.00; OOS placebo 0.03): non-announcers lag in both windows, announcers beat the scored average by a small margin, so a small announcement effect may exist but it is eaten by turnover (a third of the book changes every month). Correlation with low accruals 0.22, sales/price -0.17, R&D 0.10; 38% tech/health.

### Plain English
- **Buying the stocks that are about to report earnings** did slightly better than average in both periods (+0.4% and +1.1% a year), but far too little to clear the bar and not at all after trading costs, because the portfolio turns over a third of its names each month. The effect looks real but too small to trade.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
