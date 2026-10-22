# Round 27: receivables and inventory build-ups (2026-10-22)

Garret said on 2026-10-22 to keep searching until more rules pass. Ideas chosen by the thread. Hypotheses 184-186; 183 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Low accruals (the one pass) is a sum of balance-sheet build-ups. Sloan (1996) and later work split accruals into parts; two parts have their own literature:
- **Receivables growth ahead of sales** (Lev-Thiagarajan 1993 fundamental signals; Dechow-Ge-Larson-Sloan): customers owing more than sales growth explains is a sign of aggressive revenue recognition.
- **Inventory build-up** (Thomas-Zhang 2002 "Inventory changes and future returns"): rising inventory predicts weaker returns.
These are branches off the proven rule: if the accruals edge comes mostly from these parts, one of them should pass on its own and may be cleaner; if not, the edge sits in the cash-flow gap.

## Common setup
Round 25/26 setup exactly (annual first-filed 10-K values usable after filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names). Instant values (receivables, inventory) are the 10-K balance at fiscal year end; the prior year is the balance 335-395 days earlier. Revenue is Revenues if reported, else RevenueFromContractWithCustomerExcludingAssessedTax, annual flow.
- 184 `lowdar_quintile`: lowest (receivables - prior receivables) / assets.
- 185 `lowdinv_quintile`: lowest (inventory - prior inventory) / assets, among names reporting inventory.
- 186 `lowexcessar_quintile`: lowest (receivables growth - revenue growth), both year over year, prior receivables and revenue above 0.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors and correlation of monthly active return with low accruals. A pass whose correlation with low accruals exceeds 0.7 counts as the same bet, not a new rule.

## Multiple testing
Three rules, no variants. Total tested after this round: 186.

## Results (run 2026-10-22)

**Verdict: all three rejected (hypotheses 184-186).** Tests after this round: 186. `backtests/round27_tests/`. Check: the low-accruals reference reproduces (IS +2.8%, OOS +3.2%).

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| Reference, low accruals | +2.8% (0.51, 0.99) | +3.2% (0.60, 0.97) | passes (round 25) |
| 184 low receivables increase / assets | +2.0% (0.37, 0.93) | +0.3% (0.05, 0.61) | rejected: nothing since 2023 |
| 185 low inventory increase / assets | +3.0% (0.60, 0.98) | -2.5% (-0.56, 0.10) | rejected: edge reversed since 2023 |
| 186 low receivables growth minus revenue growth | -2.3% (-0.49, 0.06) | +0.6% (0.12, 0.63) | rejected: no edge |

Mirrors (report only): the high-receivables-increase quintile earned +3.2% IS and +9.6% OOS (placebo 1.00 both), the opposite sign to the literature. It is a post-hoc lead found in this window, so it cannot be confirmed here; the 186 mirror (+0.3%/+1.3%) and the inventory mirror (+1.3%/+5.3%) point the same way weakly. Correlation with low accruals: 0.16, 0.23, 0.20, so none repeats the accruals bet. Coverage: receivables 296 and inventory 266 of 503 members at the end.

### Plain English
- **Companies with a small rise in money owed by customers** did no better than average since 2023.
- **Companies with a small rise in inventory** did well in 2017-22 and badly since, so the edge did not last.
- **Receivables growing faster than sales** (a classic warning sign) showed no usable signal either way.
- Side hint, not a result: the companies whose customer balances grew the most did unusually well (+9.6%/yr since 2023). It was found after the fact, so it needs another era (Sharadar) before anyone treats it as real.
