# Round 56: do the three passes replicate in the S&P 600? (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 259-261; 258 were tested before this round. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the constituent list and the number of symbols with SEC and price data were looked at.

## Why this test
Every pass so far was found and tested on the same 503 large companies over the same ten years, with 258 tests behind them. A rule that is real should also work in a different set of companies over the same period. The S&P 600 (small caps) shares none of the S&P 500 names, so it is a genuinely new sample: it cannot repair a flaw in the original universe (current members only, 2017-2026), but a rule that works in both is much less likely to be luck, and one that fails in the S&P 600 is more likely to be luck or a large-cap-only effect. This is a replication test, not a search: the three rules are copied exactly, no variants.

## Universe
Current S&P 600 members from Wikipedia (600 symbols with a CIK; the S&P 400 table gives CIKs for only 120 of 400 names and was dropped), 2017-01-31 to 2026-09-30 monthly decisions. Daily bars (adjusted and raw) from Alpaca and annual facts from SEC XBRL, the same loaders as rounds 25-36. Same survivorship limitation as the S&P 500 tests, and stronger: current small-cap members are survivors that grew into the index, which flatters every rule alike (the benchmark is the equal-weight scored names) and can interact with quality signals; disclosed, not corrected. Small caps cost more to trade than large caps; the bar's 10 bps requirement (net active above 0) is the one to read.

## Rules, copied from the S&P 500 passes (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 259 `smallcap_lowaccruals`: lowest accruals / assets, round 25 definition.
- 260 `smallcap_rnd`: highest R&D / assets among names with positive R&D, round 28 definition.
- 261 `smallcap_salesprice`: highest sales / market value, round 36 definition.
Mirrors (lowest 20%) reported, not judged. Minimum 20 scored names per month. Rules with fewer R&D reporters than 20 on a date are in cash on that date.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps; IS 2017-22, OOS 2023+. A rule that passes is called replicated; a rule that fails in either window is called not replicated. No change to the S&P 500 conclusions follows from a non-replication by itself (large caps can differ), but a replication would be strong evidence the rule is not luck.

## Multiple testing
Three rules, copied, no variants. Total tested after this round: 261 (the S&P 500 pass count does not change).

## Results (hypotheses 259-261, total tested 261)

| Rule | IS net active | OOS net active | OOS placebo | Verdict |
|---|---|---|---|---|
| Low accruals | +77.0% | +3.2% (IR 0.31) | 0.79 | FAIL (OOS placebo) |
| R&D intensity | +14.5% | -6.4% | 0.75 | FAIL |
| Sales/price | +103.5% | +30.1% | 1.00 | Mechanical PASS, NOT credible |

The in-sample numbers (+77%, +103%/yr) are far outside anything real. Cause: the universe is today's S&P 600 members, i.e. small companies that were cheap in 2017 and have since grown enough to be included. That is severe survivorship/look-ahead bias, much worse than in the S&P 500 test. The sales/price "pass" and the huge IS numbers are therefore artifacts and are not counted as a pass or as replication. Fair reading: no independent confirmation; low accruals and R&D do not replicate even with the bias helping them in-sample. A real test needs point-in-time membership (Sharadar).
