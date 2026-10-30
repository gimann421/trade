# Round 50: acquisition spending and trade-credit reliance (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 247-248; 246 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the XBRL concept list used in rounds 25-49 was looked at.

## Where the idea comes from
Round 48 found, as an unregistered mirror, that names with an acquisition-completion 8-K (item 2.01) did better, the opposite of the old finding that acquirers lag (Loughran-Vijh 1997). That lead cannot be confirmed with the same data, so this round asks the question again with a different measure: the cash actually paid for acquisitions in the three most recent fiscal years, from the cash-flow statement, as a share of assets. Direction pre-registered as high = buy (the lead's direction); a negative result in either window is a plain rejection. The second rule is a balance-sheet item not used before: accounts payable over assets, a measure of how much a firm is financed by its suppliers (the mirror of the receivables and inventory items in round 27).

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 247 `acquirerspend_quintile`: sum of `PaymentsToAcquireBusinessesNetOfCashAcquired` over the latest three fiscal years that fall within the last 3.2 years before the latest annual period end, divided by assets at that period end. Highest 20%. A name with the tag reported in any year of its history but not in a given year counts 0 for that year; a name that never reports the tag is not scored.
- 248 `lowpayables_quintile`: `AccountsPayableCurrent` / assets, lowest 20%.
Annual data: latest 10-K available before the decision (filed date), no older than 455 days. Mirrors reported, not judged.

## Common setup
Round 25-49 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 248.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 247-248), wrong sign in both windows.** Tests after this round: 248. `backtests/round50_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 100 to 229 scored names per month for 247, 85 to 218 for 248.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 247 highest acquisition cash / assets (3 yrs) | -1.0% (IR -0.20, pl 0.26) | -4.4% (-0.88, pl 0.02) | rejected |
| 248 lowest accounts payable / assets | -0.4% (-0.07, pl 0.39) | -3.1% (-0.38, pl 0.12) | rejected |

Mirrors (report only): lowest acquisition spend +0.3% IS / +2.8% OOS (IR 0.06 / 0.49, OOS placebo 0.88), highest payables -1.0% / -0.9%. The mirror of 247 does not meet the bar either (IS +0.3%). Picks are tech/health heavy (66% for 247, 55% for 248) and correlate with none of the three passes (|corr| at most 0.30).

This also settles the round 48 lead: names with an acquisition 8-K did better there, yet names that spent the most cash on acquisitions did clearly worse here (-4.4% OOS). The two measures point opposite ways, so the 8-K mirror result was noise, not an acquirer effect.

### Plain English
Companies that spent heavily buying other companies did worse than average, and so did companies that lean the least on supplier credit. Neither is close. The earlier hint that acquirers do well (round 48) is not supported by this cleaner measure.
