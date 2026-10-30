# Round 53: buyback x accruals blend and industry-neutral sales/price (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 253-254; 252 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the round 49 and round 36 results (already in the repo) were used. No blend weights or industry cut-offs are tuned; each rule below is a single pre-specified construction.

## Where the idea comes from
Two of the three passes are not on the same bet (low accruals and R&D are uncorrelated with sales/price at 0.07 or less), and the best near miss, buyback yield (round 49: IS +3.5%, OOS +2.7%, OOS placebo 0.935), correlates 0.12 with low accruals. A blend of two weakly correlated ideas that each have a positive edge is the textbook way to get a stronger one, but the blend can only be judged honestly if it is specified before it is run (round 32 found no gain from combining the two earlier passes). Separately, the sales/price pass is the weakest on robustness: its within-industry in-sample was negative (-1.2%), which suggests part of it is an industry tilt. An industry-neutral version asks whether the stock-level signal survives once industry value is removed.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 253 `accbuyback_quintile`: for names with both a low-accruals score (round 25) and a buyback-yield score (round 49) on the decision date, the average of the two cross-sectional percentile ranks (highest = best); top 20%.
- 254 `spindneutral_quintile`: sales/price (round 36) minus the median sales/price of the name's 2-digit SIC group among names scored on the date, for groups with at least 5 scored names (others unscored); top 20%.
Mirrors (lowest 20%) reported, not judged.

## Common setup
Round 25-52 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet; 254 is expected to correlate with sales/price, so it counts as the same bet unless below 0.7 and it must additionally be positive within industry (reported).

## Multiple testing
Two rules, no variants. Total tested after this round: 254. The bar does not change for a blend.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 253-254).** Tests after this round: 254. `backtests/round53_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 89 to 255 scored names per month for 253 (both scores needed), 60 to 229 for 254.

**Correction before reading results:** the first run of this script divided the 2-digit SIC code by 100, which put every name in one group; the "industry-neutral" rule was then identical to plain sales/price (correlation 1.00) and showed a PASS. That run was a bug, not a result, and was discarded; the code was fixed (the SIC code in the repo is already 2-digit) and re-run with the rules and memo unchanged. Only the corrected run is reported and stored.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 253 best average rank of low accruals and buyback yield | +3.5% (IR 0.67, pl 0.99) | -1.1% (-0.18, pl 0.27) | rejected: negative since 2023 |
| 254 sales/price relative to 2-digit SIC median | +1.1% (0.12, pl 0.77) | +1.7% (0.29, pl 0.82) | rejected |

Correlations: 253 with low accruals 0.57, with sales/price 0.27; 254 with sales/price 0.81, with low accruals 0.11. Mirror of 254 (lowest sales/price within industry, report only): IS +2.1%, OOS +5.8% (IR 0.83, placebo 0.99): inside an industry the expensive-on-sales names did better in the recent period.

### What this says about the sales/price pass
Removing the industry effect cuts the sales/price edge from +4.5% / +3.3% to +1.1% / +1.7% and lets the opposite side win since 2023. So most of the sales/price pass is a bet on which industries are cheap (it favours certain industries), not stock-picking within them. That agrees with the earlier within-industry weakness (round 36) and is a reason to keep the sales/price pass flagged as weak and not to start a shadow record for it without Garret's explicit ask.

### Plain English
Blending low accruals with buyback yield did well before 2023 but lost money since, so the two do not reinforce each other recently. Comparing each company's sales-to-price only against others in its own industry largely removes the sales/price edge: it was mostly a call on which industries were cheap.
