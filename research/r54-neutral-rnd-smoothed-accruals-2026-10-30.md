# Round 54: industry-neutral R&D intensity and three-year average accruals (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause); Garret's preference is for branches off proven rules. Idea chosen by the thread. Hypotheses 255-256; 254 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the round 25, 28 and 53 results already in the repo were used. No cut-offs are tuned.

## Where the idea comes from
Round 53 showed that sales/price was largely an industry tilt. The same question is open for R&D intensity (round 28/30: mostly a tech and health bet, "likely sector luck" in the pass note). If R&D intensity relative to its own industry still earns its edge, the second pass is a stock-level signal; if not, it is an industry call and the shadow record should be read that way. The accruals pass was shown to hold within industry (round 25: +2.8% / +4.1%), so for that rule the open question is noise: a single year of accruals is a noisy measure of earnings quality, and averaging three years should reduce that noise (Sloan 1996 uses one year; later work finds multi-year measures more persistent). Both rules are one-step branches of passes already accepted.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 255 `rndneutral_quintile`: R&D / assets (names with positive R&D, round 28 definition) minus the median R&D / assets of its 2-digit SIC group among R&D reporters on the date; groups with at least 5 reporters; top 20%.
- 256 `accsmooth_quintile`: the mean of -(net income - operating cash flow) / assets over the latest fiscal year available at the decision date and up to the two before it (consecutive annual reports in the data, at least 2 years); top 20% (highest = lowest accruals).
Mirrors (lowest 20%) reported, not judged.

## Common setup
Round 25-53 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet: 255 and 256 are expected to correlate with their parents, so a pass is reported as a more robust version of the parent, not as a new, independent pass.

## Multiple testing
Two rules, no variants. Total tested after this round: 256.

## Results (run 2026-10-30)

**Verdict: both clear the numeric bar in both windows, but both are the same bet as their parents (correlation above 0.7), so by the pre-registered rule neither counts as a new, independent pass.** Tests after this round: 256. `backtests/round54_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 91 to 155 scored names per month for 255 (R&D reporters in groups of 5 or more), 177 to 415 for 256.

| Rule | IS | OOS | Bar | Same bet? |
|---|---|---|---|---|
| 255 R&D / assets relative to 2-digit SIC median | +6.2% (IR 0.67, pl 1.00, 10 bps +6.1%) | +18.0% (1.76, pl 1.00, 10 bps +18.0%) | passes | yes: corr 0.92 with R&D intensity |
| 256 three-year average accruals (lowest) | +2.6% (0.39, pl 0.99, 10 bps +2.5%) | +5.1% (0.98, pl 1.00, 10 bps +5.1%) | passes | yes: corr 0.79 with low accruals |

Mirrors (report only): 255 lowest relative R&D -0.7% / -4.7%; 256 highest accruals -0.5% / +0.7%. Correlation of 255 with low accruals 0.37 and sales/price -0.48; 256 with R&D 0.52 and sales/price -0.19. Tech/health share of picks: 99% for 255 (R&D reporting names are almost all tech, health and equipment makers, so the industry groups are inside that sector), 44% for 256.

### What this adds
- **R&D intensity is not just an industry call.** Ranked only against its own 2-digit industry peers, the R&D edge does not shrink (IS +6.2% vs +5.5%, OOS +18.0% vs +15.8%). The earlier concern that the second pass was mostly a sector bet is partly answered: within the R&D-heavy sector the high spenders still beat the low spenders. It remains a bet inside tech, health and equipment makers (99% of picks), and it still needs the Sharadar recheck; sector luck since 2023 is the open risk.
- **Smoothing accruals over three years helps.** Same idea as the low-accruals pass, less noisy: OOS rises from +3.2% to +5.1% and IR from 0.60 to 0.98, with in-sample the same (+2.6% vs +2.8%). It is a candidate for a better definition of the existing shadow rule, not a second rule. It was chosen as a variant of a known pass, so its improvement is partly selection: with 256 tests run, the better-than-parent OOS number should not be read at face value.

### Plain English
Neither of these is a new rule; both are sturdier versions of rules we already track. Comparing each company's R&D spending only against its own industry kept the full edge, so the R&D result is not just "tech did well". Averaging earnings quality over three years instead of one made the accruals rule look steadier and better in the recent period. Both caveats stand: current members only, and the data needs the Sharadar recheck.
