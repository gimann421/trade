# Round 43: one-month returns split by news (2026-10-29)

Garret's standing ask (keep searching until more rules pass; relayed by the coordinator 2026-10-29, thread free to pick its direction). Idea chosen by the thread. Hypotheses 231-232; 230 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Round 42 showed that headline counts alone carry no return signal. The published idea that does use them is Chan (2003, "Stock price reaction to news and no-news"): one-month price moves that come with news continue (drift), while moves with no news reverse. Plain one-month reversal and momentum flip sign between 2017-22 and 2023+ in this repo (rounds 19-23); this tests whether splitting by news makes either side stable. Headlines come from the round 42 download (Alpaca/Benzinga), counted over the 30 calendar days strictly before the decision day.
- 231 `newsdrift_quintile`: among names with at least 5 headlines in the last 30 days, the 20% with the highest one-month (21-session) adjusted return. Direction: highest.
- 232 `nonewsreversal_quintile`: among names with at most 1 headline in the last 30 days, the 20% with the lowest one-month return. Direction: lowest. A name needs at least 20 headlines in the whole file to be scored.

## Common setup
Round 25-42 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, equal weight, benchmark equal-weight scored names (the news-defined subset), 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names (a month with fewer is skipped).

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Two rules, no variants. Total tested after this round: 232.

## Results (run 2026-10-29)

**Verdict: both rejected (hypotheses 231-232), with the usual sign flip between eras.** Tests after this round: 232. `backtests/round43_tests/`. Check: the low-accruals, R&D and sales/price references reproduce. Coverage: 267 to 370 names with at least 5 headlines per month; 34 to 100 names with at most 1 headline (the no-news side is thin, 39 months in the OOS window had at least 20 scored names).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 231 high one-month return with news | -2.7% (-0.30, 0.02) | +3.0% (0.30, 0.98) | rejected: negative in 2017-22 |
| 232 low one-month return with no news | -1.5% (-0.14, 0.41) | +10.0% (0.96, 0.99) | rejected: negative in 2017-22 |

Mirrors (report only): high return with no news +2.8% / -3.0% (232's mirror flips the other way); low return with news -0.4% / -3.7%. Correlation of 231/232 with low accruals 0.12 / 0.00, sales/price -0.25 / 0.20, R&D 0.23 / -0.07.

### Plain English
- **Winners that had news** and **losers that had no news** both lost money in 2017-22 and made money since 2023. This is the same sign flip as every other price-move idea tested; splitting by news does not make the effect stable.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
