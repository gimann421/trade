# Round 37: size and market-value balance-sheet ratios (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 219-221; 218 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Round 36 built market values at each 10-K (shares times unadjusted close, scaled by the adjusted-close ratio), which opens ratios never testable before. Round 36's pass was sales/price; these are the other things that market value gives us, chosen to be different from it:
- **Small size** (Banz 1981; Fama-French 1992): the 20% smallest S&P 500 members by market value. Direction: smallest. Within the 500 largest firms the spread is narrow, and the size premium has been weak since 1983, so this is expected to fail.
- **Assets over market value** (Tobin's q, inverted; Lang-Stulz 1994 on low q): total assets relative to what the market pays for the firm. Direction: highest (low q).
- **Liabilities over market value** (market leverage; Bhandari 1988): leverage measured against market value instead of assets. Direction: highest. Round 28 tested book leverage and rejected it.

## Common setup
Round 36 market value and fundamentals exactly (see r36 memo), current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.
- 219 `small_quintile`: smallest market value.
- 220 `assetsmv_quintile`: highest assets / market value.
- 221 `liabmv_quintile`: highest (assets - book equity) / market value.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Three rules, no variants. Total tested after this round: 221.

## Results (run 2026-10-29)

**Verdict: all three rejected (hypotheses 219-221).** Tests after this round: 221. `backtests/round37_tests/`. Check: the low-accruals, R&D and sales/price references reproduce (+2.8/+3.2%, +5.5/+15.8%, +4.5/+3.3%).

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 219 smallest market value | +5.1% (0.66, 1.00) | +0.1% (0.01, 0.52) | rejected: nothing since 2023 |
| 220 highest assets / market value | -0.1% (-0.01, 0.38) | +1.9% (0.23, 0.86) | rejected |
| 221 highest liabilities / market value | +1.2% (0.10, 0.70) | +2.6% (0.33, 0.93) | rejected: IS fails everything, OOS placebo 0.931 |

Mirrors (report only): largest market value -2.3% / +3.6%; lowest assets/market value +2.9% / +4.6% (passes on its own numbers in neither direction as a pre-registered rule, so not counted); lowest market leverage +3.3% / +2.6%. Correlation with sales/price: 0.61, 0.74, 0.70, so 220 and 221 would have been the same bet as the third pass anyway. With low accruals: 0.03, 0.07, 0.06. With R&D: -0.33, -0.42, -0.41. Tech/health share of picks: 34%, 6%, 7%.

### Plain English
- **Smallest companies** won big in 2017-22 (+5.1%/yr) and did nothing since 2023, the usual fate of the size effect.
- **Assets or debt relative to market value** did not work; both are mostly the same bet as sales/price.
- Still three independent rules: low accruals, R&D intensity, and (a weaker pass) sales/price.
