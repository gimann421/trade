# Round 69: segment focus (2026-11-05)

Idea 5 of the second Opus idea list (`/mnt/project-files/research/opus-new-ideas-round2-ranked-2026-11-05.md`, requested by Garret 2026-11-05) as hypothesis 285 (the lobbying rules of round 68, whose data was still downloading, took 286 and 287 when registered afterwards). 284 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of this test was computed.** No return of this rule was looked at before writing it.

## Data and its limits (stated before the run)
SEC Financial Statement Data Sets, original 10-Ks of current members from 2015q4. Business-segment revenue = USD revenue facts for the fiscal year (4 quarters, ending on the filing's period date, no co-registrant) whose segments string uses the `BusinessSegments` axis alone (optionally with `ConsolidationItems`). The revenue tag with the most segment members is used; members whose name contains other / eliminations / corporate / unallocated / intersegment / reconciling / total / consolidated and non-positive values are dropped. Companies that report segments under a custom axis, or that disclose segments in a way that is not tagged on revenue, look like single-segment companies and get 1.0: this misclassification adds noise to a rule that is about segments, which is the main weakness and is not corrected. Only the original 10-K values are used (no restated or later amended figures), so the 2023 segment-reporting update does not change anything within a filing already used.

## Rule (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 287 `segfocus_quintile`: Herfindahl index (sum of squared revenue shares) over the business segments of the latest original 10-K filed before the decision day and ending within 455 days. Two or more segments: the index; no segment facts but a consolidated revenue fact for the fiscal year: 1.0 (single segment); no revenue fact: unscored. Hold the highest 20% (most focused). Ties: the harness breaks ties alphabetically by ticker, which would make a tied top fifth an arbitrary alphabetical slice. So for this rule the holding is every name whose score is at least the score of the 20th-percentile cut-off name (the basket can therefore hold more than 20% of scored names when many tie at 1.0); the mirror uses the same tie rule on the lowest scores. Equal weight.

## Common setup
Round 25-68 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirror (least focused); correlation with the three passes; tech/health share; number of scored names and of names at exactly 1.0. Correlation above 0.7 with an existing pass means the same bet.

## Multiple testing
One rule, no variants. Total tested after this round: 285.

## Results (run 2026-11-05)

**Verdict: rejected (hypothesis 285).** Tests after this round: 285. `backtests/round69_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). 287-471 names scored per month, of which 106-154 sit at exactly 1.0 (single segment as seen by the parser), so the top fifth is the tied top group of single-segment names.

| Rule | IS 2017-22 | OOS 2023+ | Verdict |
|---|---|---|---|
| 285 most focused (single segment or highest concentration) | -0.5% (IR -0.20, pl 0.23) | -0.1% (IR -0.04, pl 0.41) | rejected: nothing |

Reported, not judged: mirror (least focused) IS -0.1%, OOS -0.5%. Correlation with low accruals 0.30, R&D 0.57, sales/price -0.38. Tech/health share 39%. A caveat from the memo stands: companies tagging segments in a way the parser does not read are scored as single-segment, which adds noise.

### Plain English
Companies with one dominant business did no better than diversified ones, in either period, and neither did the reverse. No pass.
