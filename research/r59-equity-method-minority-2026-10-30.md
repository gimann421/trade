# Round 59: equity-method income and minority interests (2026-10-30)

Garret's standing ask (keep searching until more rules pass; coordinator re-relayed 2026-10-30, do not pause). Idea chosen by the thread. Hypotheses 266-267; 265 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of this test was computed.** Only the XBRL concept list used in rounds 25-58 was looked at.

## Where the idea comes from
Two corporate-structure items not used in any earlier round. (1) Income from equity-method investments (stakes in affiliates, reported as one profit line) over assets: profit the market cannot see inside, which may be under-valued (compare round 40 on affiliate ownership, which used filings, not this line). (2) Minority (noncontrolling) interests over assets: a complex group structure where part of the profit belongs to outsiders; the simpler structure (lowest share) is the buy side. Directions pre-registered: 266 highest equity-method income/assets = buy; 267 lowest minority interest/assets = buy. Names that never report the tag are not scored, so coverage will be thin. Mirrors reported, not judged.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 266 `equitymethod_quintile`: `IncomeLossFromEquityMethodInvestments` (350-380 day flow, latest fiscal year) / assets. Highest 20%.
- 267 `lowminority_quintile`: -(`MinorityInterest` / assets) at the latest fiscal year end, only for names that report it in some year (a year without it counts 0 if reported in any other year).
Annual data: latest 10-K filed before the decision, no older than 455 days.

## Common setup
Round 25-58 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes; tech/health share. Correlation above 0.7 with an existing pass is the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 267.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 266-267).** Tests after this round: 267. `backtests/round59_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 68 to 124 scored names (266) and 103 to 214 (267).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 266 highest equity-method income / assets | -1.3% (IR -0.20, pl 0.29) | +1.0% (0.19, pl 0.67) | rejected |
| 267 lowest minority interest / assets | +2.8% (0.60, pl 0.948) | -0.2% (-0.06, pl 0.46) | rejected: IS just missed the placebo (0.948), nothing OOS |

Mirrors (report only): lowest equity-method income IS +3.0% (pl 0.94) / OOS +2.1% (pl 0.77), misses the bar on the placebos in both windows; highest minority interest -0.1% / +0.2%. Correlation with the three passes at most 0.33 in absolute terms.

### Plain English
Companies with big profits from stakes in affiliates did not do better, and companies with a simple ownership structure did well until 2022 and then stopped. No pass.
