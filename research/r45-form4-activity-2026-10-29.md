# Round 45: Form 4 insider filing activity (2026-10-29)

Garret's standing ask (keep searching until more rules pass; relayed by the coordinator 2026-10-29). Ideas chosen by the thread. Hypotheses 236-237; 235 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Round 44 loaded Form 4 (insider transaction report) filing dates for current S&P 500 members from 2015-10 on, complete and even across years. A Form 4 is filed within two business days of any insider purchase, sale, option exercise or grant, but its direction and size are inside the filing and not available here. So only the filing rate is used.
- **236 `formsurge_quintile`, insider activity surge** (informed-trading intensity; Jeng-Metrick-Zeckhauser 2003, Cohen-Malloy-Pomorski 2012 on opportunistic insiders): the 20% of scored names with the highest ratio of Form 4 filings in the last 90 days to the average 90-day count over the 360 days before that (names with at least 8 filings in those 360 days). Direction: highest.
- **237 `formquiet_quintile`, quiet insiders** (the opposite reading: few insider transactions means little compensation churn and no informed selling): the 20% with the fewest Form 4 filings in the trailing 365 days. Direction: fewest. The count mostly tracks the number of insiders and equity-compensation intensity, so it is expected to correlate with size and technology exposure.

The directions are fixed here; the mirrors are reported, not judged. A name needs at least 2 8-K filings in the file to be scored (excludes data gaps).

## Common setup
Round 25-44 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Two rules, no variants. Total tested after this round: 237.

## Results (run 2026-10-29)

**Verdict: both rejected (hypotheses 236-237).** Tests after this round: 237. `backtests/round45_tests/`. Check: the low-accruals, R&D and sales/price references reproduce. Coverage 329 to 502 scored names per month.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 236 highest Form 4 surge | -1.0% (-0.26, 0.29) | -2.0% (-0.50, 0.12) | rejected: wrong sign in both windows |
| 237 fewest Form 4 filings | +1.5% (0.34, 0.95) | -0.6% (-0.16, 0.41) | rejected: negative since 2023 |

Mirrors (report only): lowest surge +0.7% / +1.1% (placebo 0.87 / 0.89, the closest mirror, still below the bar and not pre-registered); most Form 4 filings -2.8% / +1.0%. Correlation of 237 with sales/price 0.52, R&D -0.36, low accruals 0.10; of 236 with sales/price 0.04, R&D -0.07, low accruals -0.06.

### Plain English
- **A burst of insider filings** pointed the wrong way in both periods, and **quiet insiders** made +1.5%/yr in 2017-22 but lost since 2023. Counting insider filings carries no stable signal; whether insiders bought or sold would be needed and is not in this data.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
