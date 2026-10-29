# Round 36: classic value yields (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 215-218; 214 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the idea comes from
Every one of the 214 earlier tests used fundamentals scaled by assets, or prices alone. The value factor (cheap relative to book value, earnings, cash flow or sales) was never tested because stored prices are split- and dividend-adjusted and cannot give a market value. It is the most published of all anomalies (Fama-French 1992, Lakonishok-Shleifer-Vishny 1994) and has done badly since 2007, so the prior is that it fails; Garret's standing preference is for evidence, not fame, and a rule of this size should be tested once rather than assumed dead.

## Market value
Shares outstanding at each 10-K: the cover-page count (SEC dei EntityCommonStockSharesOutstanding, filed with the 10-K); when absent, or below half of the weighted average diluted shares of that fiscal year (multi-class companies), the weighted average diluted shares. Price: the unadjusted close (Alpaca raw bars) on the filing date. At a later decision date t the market value is scaled by the adjusted-close ratio, adj(t)/adj(filing date). Fundamentals as in rounds 25-28 (first-filed 10-K values, usable after the filing date, fiscal year within 455 days). Book equity = assets - liabilities. Current S&P 500 members only.

## Rules (all: highest 20% of scored names, equal weight, monthly, benchmark equal-weight scored names)
- 215 `bookprice_quintile`: book equity / market value.
- 216 `earnprice_quintile`: net income / market value, names with positive net income.
- 217 `cfprice_quintile`: operating cash flow / market value.
- 218 `salesprice_quintile`: revenue / market value.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps; IS 2017-22, OOS 2023+; 5/10 bps costs; minimum 20 scored names. Reported, not judged: mirrors (most expensive quintile); correlation with low accruals and with R&D intensity (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Four rules, no variants. Total tested after this round: 218.

## Results (run 2026-10-29)

**Verdict: `salesprice_quintile` (hypothesis 218) PASSES the pre-registered bar; book/price, earnings/price and cash-flow/price are rejected (215-217).** Tests after this round: 218. Results in `backtests/round36_tests/`; robustness in `backtests/round36_tests/robustness.json` (`research/round36_robust.py`, written after the pass was seen: diagnostics, not new hypotheses). Check: the low-accruals and R&D references reproduce. Coverage: 341 of the 719 downloaded tickers have a usable value table (current members with SEC share counts and prices at filing); 98 to 307 names are scored per month (fewer early). The benchmark is the same scored names.

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 215 book / price | -1.0% (-0.08, 0.21) | +1.3% (0.17, 0.76) | rejected |
| 216 earnings / price | +2.2% (0.19, 0.93) | +3.5% (0.44, 0.98) | rejected: IS IR 0.19, IS placebo 0.932 |
| 217 cash flow / price | +1.5% (0.14, 0.86) | +3.4% (0.45, 0.97) | rejected |
| 218 sales / price | +4.5% (0.59, 1.00) | +3.3% (0.53, 0.97) | PASS; +4.5% / +3.2% at 10 bps |

Correlation of 218's monthly active return: with low accruals -0.02, with R&D intensity -0.51 (independent of both passes). Tech/health share of picks 11-25%. Mirror (most expensive quintile): +1.2% / +0.7%.

Flags (reported, none of them moves the verdict, and the bar is not loosened):
- 218 tests in total, and this is the 2nd of 4 value measures; the family's other three failed (book/price, the most famous, is negative), so a single pass inside it is what luck would also give.
- Not monotone in the tails: the decile is better (+7.9% / +5.1%) but the tercile is weaker (+2.5% / +1.4%, OOS placebo 0.87), and the most expensive quintile is also slightly positive.
- Within-industry (top 20% inside each SIC group) is -1.2% in 2017-22 and +1.9% since 2023: much of the effect is which industries are cheap on sales, not which companies within them.
- Concentrated in time: 2022 contributes +17.4% active; years positive 7 of 10 (2018, 2019 and 2024 negative). Since 2023 the first half (2023-24) is only +1.0% (placebo 0.71) and the second half +5.8%.
- Current S&P 500 members only (survivorship); recheck on Sharadar when it arrives.

### Plain English
- Buying the 20% of large US companies that are cheapest relative to their sales beat the average company by about 4.5%/yr in 2017-22 and 3.3%/yr since 2023. It is a different bet from the two earlier rules (not tech, not accruals).
- The famous version, cheap relative to book value, did not work, and earnings or cash-flow cheapness fell just short. That makes the sales result more likely to be partly luck, and it leans on a few industries and on 2022, so it is a weaker pass than the first two.
