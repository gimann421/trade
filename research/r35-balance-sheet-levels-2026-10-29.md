# Round 35: liquidity, earned capital and treasury stock (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 212-214; 211 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
All three earlier passes and near-passes were flows or intensities measured over assets (accruals, R&D, cash, stock pay). These are balance-sheet levels, which are less tied to technology companies, and each has a published basis. Insider-trading data (Form 4) was the first idea considered but www.sec.gov is blocked in this environment (403 without the contact email), so it was dropped.
- **Current ratio, highest quintile** (Altman 1968 liquidity component; Ou-Penman 1989 on ratio-based signals): current assets over current liabilities. Direction: highest.
- **Retained earnings over assets, highest quintile** (Altman Z score "earned capital"; firm maturity per DeAngelo-DeAngelo-Stulz 2006 "life-cycle theory of dividends"): accumulated profits as a share of assets. Direction: highest.
- **Treasury stock over assets, highest quintile** (cumulative repurchases kept as treasury stock; Ikenberry-Lakonishok-Vermaelen 1995 on repurchases; the level, not the flow, which round 18 tested): firms with a large past buyback record. Direction: highest. Only names with the tag are scored.

## Common setup
Round 25-34 setup exactly (annual first-filed 10-K balance values usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names).
- 212 `currentratio_quintile`: highest AssetsCurrent / LiabilitiesCurrent (liabilities above 0).
- 213 `retained_quintile`: highest RetainedEarningsAccumulatedDeficit / assets.
- 214 `treasury_quintile`: highest TreasuryStockValue / assets (positive values only).

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals and with R&D intensity (above 0.7 means the same bet, not a new rule); tech/health share of the picks.

## Multiple testing
Three rules, no variants. Total tested after this round: 214.

## Results (run 2026-10-29)

**Verdict: all three rejected (hypotheses 212-214); `currentratio_quintile` is a borderline near miss that fails on a single criterion and is not rescued.** Tests after this round: 214. `backtests/round35_tests/`. Check: the low-accruals and R&D references reproduce.

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 212 highest current ratio | +2.0% (0.33, 0.94) | +7.7% (0.82, 1.00) | rejected: IS placebo 0.942 is below 0.95 (all other criteria met) |
| 213 highest retained earnings / assets | +1.6% (0.39, 0.95) | -1.2% (-0.27, 0.19) | rejected |
| 214 highest treasury stock / assets | +3.2% (0.52, 1.00) | +0.7% (0.11, 0.58) | rejected: nothing since 2023 |

Borderline flag for 212: the 2017-22 net active is +2.0% (right at the bar) and the placebo falls 0.008 short; the bar is not loosened. Its monthly active return correlates 0.66 with R&D intensity (just under the 0.7 same-bet line) and 65% of its picks are tech and health names, so even a clean pass would have been mostly the R&D bet. Mirrors (report only): lowest current ratio -3.7% / -4.1%; lowest retained earnings +0.5% / +1.9%; lowest treasury stock -2.2% / -1.5%. Correlation with low accruals: 0.24, -0.09, 0.10. With R&D intensity: 0.66, 0.28, 0.30.

### Plain English
- **Companies with strong short-term liquidity** came very close: +2.0%/yr in 2017-22 and +7.7%/yr since 2023. It missed the strict bar by a hair on one chance check, and it is largely the same tech and health-care names as the R&D rule, so it would not have been an independent rule anyway.
- **Companies with large accumulated profits** and **companies with a big past buyback record** did not hold up since 2023.
- Still two independent rules: low accruals and R&D intensity.
