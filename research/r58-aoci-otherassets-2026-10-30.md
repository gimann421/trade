# Round 58: accumulated other comprehensive income and opaque assets (2026-10-30)

Garret's standing ask (keep searching until more rules pass; coordinator re-relayed 2026-10-30, do not pause). Idea chosen by the thread. Hypotheses 264-265; 263 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of this test was computed.** Only the XBRL concept list used in rounds 25-57 was looked at.

## Where the idea comes from
Two balance-sheet items not used in any earlier round. (1) Accumulated other comprehensive income over assets: gains and losses that bypass the income statement (foreign currency translation, pension, securities); a large positive balance means an unbooked tailwind that may not be priced. (2) Other non-current assets over assets: a catch-all line that hides what the company owns; less transparent balance sheets may be penalised by the market, so the lowest share is the buy side. Directions pre-registered: 264 highest AOCI/assets = buy; 265 lowest other non-current assets/assets = buy. Mirrors are reported, not judged.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 264 `aoci_quintile`: `AccumulatedOtherComprehensiveIncomeLossNetOfTax` at the latest fiscal year end / assets. Highest 20%.
- 265 `lowotherassets_quintile`: -(`OtherAssetsNoncurrent` / assets). Names with no such fact are not scored.
Annual data: latest 10-K filed before the decision, no older than 455 days.

## Common setup
Round 25-57 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes; tech/health share. Correlation above 0.7 with an existing pass is the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 265.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 264-265).** Tests after this round: 265. `backtests/round58_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 264 highest AOCI / assets | +2.1% (IR 0.47, pl 0.91) | +1.6% (0.29, pl 0.81) | rejected: positive in both windows but short of the bar (IS placebo, OOS net active, IR, placebo) |
| 265 lowest other non-current assets / assets | +1.8% (0.37, pl 0.83) | -3.3% (-0.73, pl 0.06) | rejected: wrong sign OOS |

Mirrors (report only): lowest AOCI -0.5% / -4.9%; highest other non-current assets -1.1% IS but +5.5% OOS (IR 1.26, pl 0.99), a sign flip, so noise. Correlation with the three passes at most 0.34 in absolute terms.

### Plain English
Companies with large unbooked gains stored in "other comprehensive income" did a little better than average in both periods, but by too little to count and not clearly beyond luck. Companies with a small "other assets" line did worse recently. No pass.
