# Round 52: other non-operating income and intangible amortization (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 251-252; 250 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the XBRL concept list used in rounds 25-51 and the earlier price-factor list were looked at.

## Where the idea comes from
Earnings that include large non-core items are less persistent (Sloan 1996 for accruals generally; Burgstahler-Dichev 1997 and Bradshaw-Richardson-Sloan 2001 for non-operating components). The accruals pass shows that earnings quality matters in this universe; this round looks at two components the accruals measure does not isolate: other non-operating income or expense (`OtherNonoperatingIncomeExpense`), and amortization of acquired intangibles (`AmortizationOfIntangibleAssets`), the footprint of past acquisitions (the round 50 acquisition-cash measure was a clear loser, but acquired intangibles also build up through stock deals that the cash-flow line misses). Data: SEC XBRL, first-filed 10-K values, `data/round52/` (git-ignored).

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 251 `cleannonop_quintile`: the 20% with the smallest absolute other non-operating income or expense over assets (zero or tag missing for a name that reports the tag in another year counts as 0; a name that never reports the tag is not scored).
- 252 `lowamort_quintile`: the 20% with the lowest amortization of intangible assets over assets (same missing-value handling).
Annual data: latest 10-K available before the decision (filed date), no older than 455 days. Mirrors reported, not judged.

## Common setup
Round 25-51 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 252.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 251-252).** Tests after this round: 252. `backtests/round52_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 100 to 236 scored names per month for 251, 118 to 279 for 252.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 251 smallest abs other non-operating income / assets | +0.8% (IR 0.18, pl 0.69) | -1.6% (-0.37, pl 0.24) | rejected |
| 252 lowest intangible amortization / assets | -0.3% (-0.05, pl 0.39) | +3.8% (0.70, pl 0.97) | rejected: in-sample negative |

Rule 252 is a textbook sign flip: its mirror (highest amortization) did +3.4% before 2023 (IR 0.64, placebo 0.99) and -3.8% since (IR -0.82), the reverse of the low-amortization rule in each window. Neither direction holds in both. Correlation with the three passes at most 0.32.

### Plain English
Companies with the cleanest non-operating income did nothing. Companies with the least amortization of acquired intangibles did well only since 2023, while the opposite group did well before 2023, so the effect swapped sign between eras and cannot be relied on.
