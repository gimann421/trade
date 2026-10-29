# Round 41: depreciation intensity and deferred revenue (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 226-227; 225 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Two accounting levers not yet used in rounds 25-40, both from SEC annual data over assets:
- **Depreciation and amortization over assets, highest quintile** (the capital-intensity and asset-age signal; Titman-Wei-Xie 2004 on investment, Hirshleifer et al. on asset intensity): firms whose assets are being used up fast. Direction: highest.
- **Deferred revenue over assets, highest quintile** (customers paid in advance; Barth-Beaver-Landsman on deferred revenue as a leading indicator, and the revenue-quality literature): cash collected before sales are recognized. Direction: highest. DeferredRevenue when reported, otherwise ContractWithCustomerLiability (post-2018 tag).

## Common setup
Round 25-40 setup exactly: first-filed annual values (flows 350-380 days, instants at fiscal year end), usable after the 10-K filing date, fiscal year within 455 days, assets from the earlier tables, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names. Only names with the tag are scored.
- 226 `dna_quintile`: highest DepreciationDepletionAndAmortization / assets (non-negative values).
- 227 `defrev_quintile`: highest deferred revenue (or contract liability) / assets (positive values).

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals and R&D intensity (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Two rules, no variants. Total tested after this round: 227.

## Results (run 2026-10-29)

**Verdict: both rejected (hypotheses 226-227).** Tests after this round: 227. `backtests/round41_tests/`. Check: the low-accruals and R&D references reproduce. Coverage: D&A 184 to 288 scored names; deferred revenue only 18 to 23 names in 2017-18 (below the 20-name minimum in some months, so the early window is thin), 128 to 165 from 2020.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 226 highest D&A / assets | +0.6% (0.11, 0.72) | -0.5% (-0.11, 0.35) | rejected |
| 227 highest deferred revenue / assets | +1.1% (0.15, 0.70) | +3.8% (0.40, 0.93) | rejected: IS fails, OOS placebo 0.932 |

Mirrors (report only): lowest D&A -0.6% / +5.0%; lowest deferred revenue +0.7% / +1.5%. Correlation with R&D: -0.17 and 0.57 (227 is 76% tech/health); with low accruals 0.39 and 0.40.

### Plain English
- **Companies whose assets are wearing out fastest** and **companies holding the most customer prepayments** did not beat the average. The prepayment one is mostly software names, as with R&D.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
