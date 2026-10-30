# Round 48: 8-K event types (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30, with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 241-243; 240 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the counts of 8-K item codes across all names (27 item types, from the round 44 download) were looked at.

## Where the idea comes from
Round 35 tested the count of 5.02 (officer/director changes) 8-Ks and the total count of 8-Ks; the specific event classes were never separated. Events that signal trouble (restructuring, impairments, auditor changes, non-reliance on past financials, delisting notices, bankruptcy-type items), large acquisitions (acquirers have long been reported to lag; Loughran-Vijh 1997) and new debt obligations (leverage raising; Spiess-Affleck-Iskoe 1999 on debt issuers) are the plausible negative classes. Each rule holds the names with none of the class, so it is an avoidance rule. Data: round 44 SEC submissions (8-K item codes), 2015-10 on. Because the file starts in 2015-10, the 730-day window for item 2.01 is only partially covered at the first decisions in 2017 (15 to 24 months); disclosed, not corrected.

## Rules (equal weight, all picked names; the harness name "quintile" is kept but the portfolio is not a quintile)
- 241 `nodistress_quintile`: no 8-K with any of items 1.02, 1.03, 2.04, 2.05, 2.06, 3.01, 4.01, 4.02 in the trailing 365 days.
- 242 `noacquirer_quintile`: no 8-K with item 2.01 in the trailing 730 days.
- 243 `nonewdebt_quintile`: no 8-K with item 2.03 in the trailing 365 days.
A name is scored if at least 6 8-Ks of any kind are in the file. Benchmark: equal-weight scored names. Direction: names without the event. Mirrors (names with the event) are reported, not judged.

## Common setup
Round 25-47 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet.

## Multiple testing
Three rules, no variants. Total tested after this round: 243.

## Results (run 2026-10-30)

**Verdict: all three rejected (hypotheses 241-243).** Tests after this round: 243. `backtests/round48_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 338 to 501 scored names per month.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 241 no distress 8-Ks | -0.1% (IR -0.11, pl 0.36) | -0.3% (-0.34, 0.23) | rejected |
| 242 no completed acquisition 8-K | -0.2% (-0.31, 0.21) | -0.4% (-0.57, 0.09) | rejected |
| 243 no new-debt 8-K | -0.2% (-0.12, 0.40) | +0.2% (0.10, 0.62) | rejected |

Mirrors (report only): names with a 2.01 acquisition 8-K did +0.7% IS and +2.5% OOS (IR 0.28 / 0.60, OOS placebo 0.94), the opposite of the literature; since it was not a pre-registered direction and misses the bar in-sample, it is a lead only, not a result. Distress and debt mirrors are small.

### Plain English
Steering away from companies that filed warning-type or acquisition or new-debt notices did nothing: such names did as well as or slightly better than the rest. Acquirers actually did a bit better, especially since 2023, which is the reverse of the old finding. No new pass; the three earlier passes stand.
