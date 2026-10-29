# Round 42: news attention and headline tone (2026-10-29)

Resumed at Garret's standing ask (keep searching until more rules pass; relayed by the coordinator 2026-10-29 with the thread free to pick its own direction, news-based signals allowed). Ideas chosen by the thread. Hypotheses 228-230; 227 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
A source none of the 227 earlier tests used: the Alpaca (Benzinga) news feed, available for every ticker back to 2016. For each S&P 500 member the trailing headlines are counted and scanned at each month-end decision, using only headlines published before the decision date (US/Eastern timestamps, strictly earlier calendar day).
- **228 `nonews_quintile`, no-news premium** (Fang-Peress 2009, "Media coverage and the cross-section of stock returns"): the 20% of scored names with the fewest headlines in the trailing 90 days. Direction: fewest. Count is not size-adjusted; the correlation with size is reported.
- **229 `attentionfade_quintile`, abnormal attention reverses** (Barber-Odean 2008; Da-Engelberg-Gao 2011): the 20% with the lowest ratio of the last 30 days of headlines to the average 30-day count over the 330 days before that (names with at least 12 headlines in those 330 days). Direction: lowest abnormal attention, on the reasoning that attention spikes overprice.
- **230 `goodtone_quintile`, headline tone** (Tetlock 2007; Tetlock-Saar-Tsechansky-Macskassy 2008): the 20% with the lowest share of negative headlines in the trailing 90 days, among names with at least 5 headlines. A headline is negative if it contains any of: downgrade, downgrades, cut, cuts, lowers, lowered, miss, misses, lawsuit, sues, probe, investigation, recall, plunge, plunges, falls, slump, slumps, warns, warning, fraud, bankruptcy, layoffs, loses, drops. Direction: lowest negative share. Words fixed here, before any result.

## Common setup
Round 25-41 setup exactly: current S&P 500 members at each date (point-in-time membership as in earlier rounds), monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names. A name is scored only if the feed returned at least one headline for it in the data (otherwise a data gap is indistinguishable from no news); for 228 the ticker must have at least 20 headlines in the whole 2016-2026 file.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Three rules, no variants. Total tested after this round: 230.

## Results (run 2026-10-29)

**Verdict: all three rejected (hypotheses 228-230).** Tests after this round: 230. `backtests/round42_tests/`. Check: the low-accruals, R&D and sales/price references reproduce. Coverage: 500 or more scored names per month for 228 and 229 after the first year (the feed has a headline history for nearly every ticker), 444 to 497 for 230. News download: 719 tickers, Alpaca (Benzinga) headlines 2016-10 to 2026-10-29; the first runs hit rate limits on the heaviest tickers, which were re-fetched with fewer workers until none failed, so no ticker is missing.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 228 fewest headlines (no-news premium) | -0.1% (-0.02, 0.56) | -2.7% (-0.54, 0.04) | rejected: wrong sign since 2023 |
| 229 lowest abnormal attention | -4.1% (-1.02, 0.00) | -3.1% (-0.72, 0.06) | rejected: wrong sign in both windows |
| 230 lowest negative-headline share | -0.9% (-0.18, 0.23) | +0.2% (0.03, 0.62) | rejected |

Mirrors (report only): most headlines +1.5% / +6.2% (the well-covered large names beat the average since 2023, i.e. mega-cap strength, not a no-news premium); highest abnormal attention -1.5% / -3.1%; highest negative-headline share -0.8% / -0.7%. Correlation with low accruals: -0.58, -0.08, -0.05; with sales/price 0.16, 0.06, -0.51; with R&D -0.39, -0.10, 0.39.

### Plain English
- **Companies with no news coverage**, **companies whose news attention has faded**, and **companies with the fewest bad headlines** all failed. The news-volume effect points the opposite way to the published "no-news premium": heavily covered names did better, most clearly since 2023.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
