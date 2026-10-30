# Round 51: nominal share price level (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 249-250; 248 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the list of earlier price-based factors (momentum, reversal, volatility, beta, 52-week high, dollar volume, turnover, skew, MAX) was checked; the raw (unadjusted) closing-price files from round 36 exist for all 719 tickers.

## Where the idea comes from
Nominal share price (not market value) has been reported to matter on its own: investors treat a low price per share as cheap and a high one as expensive ("nominal price illusion", Birru-Wang 2016, JFE: low-priced stocks are overpriced, high-priced stocks underpriced relative to fundamentals, after controlling for size; related: Dyl-Elliott 2006 on share price and shareholder base). It is a pure price-level feature, unrelated to the fundamentals-based passes, and was never tested here. The raw closing price is the actual quote, not the split-adjusted one.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names; both judged)
- 249 `lowprice_quintile`: the 20% of priced current members with the lowest raw close on the decision day.
- 250 `highprice_quintile`: the 20% with the highest raw close (the mirror, judged here because the literature's sign for large caps is the reverse of the small-cap folklore).
Both are judged, so the two rules cannot both be luckily right, only one can pass; counted as two tests.

## Common setup
Round 25-50 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 250.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 249-250).** Tests after this round: 250. `backtests/round51_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 501 to 503 priced names every month.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 249 lowest raw share price | -0.2% (IR -0.02, pl 0.60) | -0.1% (-0.01, pl 0.49) | rejected |
| 250 highest raw share price | +0.7% (0.10, pl 0.74) | -1.6% (-0.24, pl 0.12) | rejected |

The two rules are exact mirrors of each other. Low-price names correlate 0.67 with sales/price and high-price names -0.70 (a little value overlap) and have no edge of their own. Tech/health share of picks 16% (low) and 51% (high).

### Plain English
Whether a stock trades at a low or a high price per share made no difference to how it did; the cheap-looking and expensive-looking share prices both came out around average. Nothing to add to the three passes.
