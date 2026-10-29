# Round 38: filing timeliness (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 222-223; 221 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
A different kind of input: not a number inside the accounts but when the accounts arrive. Every earlier round measured what a firm reports; none used how fast. Late annual reports are linked to poor information environments and bad news (Givoly-Palmon 1982 on reporting lags; Alford-Jones-Zmijewski 1994 on late filing and returns; Bartov-Konchitchki on timeliness), so early filers are expected to do better than late ones. Both measures come from the filing dates already in the SEC facts, no new download.
- 222 `earlyfiler_quintile`: the 20% of scored names with the fewest days from fiscal year end to first 10-K filing. Direction: fewest days.
- 223 `speedup_quintile`: the 20% with the largest speed-up against the year before (days last year minus days this year). Direction: largest speed-up. Needs two consecutive fiscal years.

## Common setup
Round 25-37 setup exactly: first-filed 10-K, usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names. Known limit: large S&P 500 firms are all accelerated filers with a 60-day deadline, so the spread is narrow and mostly reflects fiscal calendar and company habit.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirror (late filers, slowest); correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Two rules, no variants. Total tested after this round: 223.

## Results (run 2026-10-29)

**Verdict: both rejected (hypotheses 222-223).** Tests after this round: 223. `backtests/round38_tests/`. Check: the low-accruals, R&D and sales/price references reproduce.

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 222 earliest 10-K filers | +0.7% (0.15, 0.72) | +4.0% (0.93, 1.00) | rejected: nothing in 2017-22 |
| 223 largest filing speed-up | +0.4% (0.13, 0.65) | -1.1% (-0.35, 0.24) | rejected |

Mirrors (report only): slowest filers -0.5% / -0.8%; least speed-up -1.1% / +0.2%. Correlation of 222 with R&D 0.64 (59% of its picks are tech/health, early filing is a tech habit), with low accruals 0.45, with sales/price -0.49. Of 223: 0.31, 0.27, -0.05.

### Plain English
- **Companies that file their annual report earliest** did well since 2023 (+4.0%/yr) but nothing in 2017-22, and the early filers are mostly the same tech and health names as the R&D rule.
- **Companies that filed faster than a year before** did not beat the average.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
