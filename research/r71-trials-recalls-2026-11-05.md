# Round 71: trial catalysts and product recalls (2026-11-05)

Ideas 9 and 10 of the second Opus idea list (`/mnt/project-files/research/opus-new-ideas-round2-ranked-2026-11-05.md`, requested by Garret 2026-11-05) as hypotheses 288 and 289 (registered before the round 70 text rules, whose download was still running, so those took 290 and 291). 287 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of these tests was computed.** No return of either rule was looked at before writing it. The number of matched names (below) was looked at, because it decides whether 290 is testable.

## Data and its limits (stated before the run)
- Universe: current S&P 500 members whose 2-digit SIC is 28 (chemicals and drugs) or 38 (instruments and devices): 73 members. Companies in consumer products and autos, which the idea list also named, are **not covered** because the CPSC and NHTSA recall pulls were not built; this narrows idea 10 to health care.
- Trials (ClinicalTrials.gov v2 API): Phase 2 and Phase 3 interventional studies whose lead sponsor, normalised (case, punctuation and company suffixes removed), equals or starts with the normalised SEC name or one of its three most recent former names. No hand matching (the list suggested hand matching; this is not done). 4,862 studies matched, for 22 of the 73 members, of which only about 10 are drug makers with sizeable programs; companies such as Eli Lilly and Merck (sponsor names written differently) are largely missed.
- **Look-ahead caveat for 288:** the registry returns the current primary completion date, not the date planned at the time. A trial planned for a date that later slipped is placed in the wrong year, and trials terminated early are counted by their actual end. The test therefore knows slightly more than a trader could have known and can only flatter the idea; a pass would not be trusted without a forward record.
- Recalls (openFDA drug and device enforcement reports, report dates 2012-06 on): recalling-firm name equals the normalised SEC name or a former name. 1,793 reports matched, for 26 of the 73 members.

## Rules (equal weight)
- 288 `pipelinesoon_quintile`: among covered members with at least one matched trial and positive R&D expense in a 10-K filed before the decision day and ending within 455 days: score = (number of matched Phase 2 or 3 studies first posted on or before the decision day with primary completion date after the decision day and within the next 365 days) divided by the R&D expense in $ billions. Hold the highest 20% of scored names. **At least 20 scored names are required** (the rule's own minimum); below that the rule holds nothing and is reported as not testable on this data, which counts as a failed test. With about 22 matched members the minimum is unlikely to be met in most months.
- 289 `norecall_basket`: covered members that are priced and have no matched drug or device enforcement report with a report date in the 730 days up to the decision day (reports count from their report date). Equal weight; cash if fewer than 8 names. Benchmark: equal-weight priced covered members. Minimum 20 priced covered members. Because most covered members have no matched record at all (name mismatch, not necessarily no recall), the basket is close to the whole covered group by construction, which is a weakness stated here.

## Common setup
Round 25-70 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps, at least 48 / 36 rebalances. Reported, not judged: mirror of 289 (members with a recent recall); number of scored names; correlation with the three passes. Correlation above 0.7 with an existing pass means the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 289 (the round 70 text rules add two more when they run).

## Results (run 2026-11-05)

**Verdict: both rejected (hypotheses 288-289); 288 is not testable on free data.** Tests after this round: 289. `backtests/round71_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3).

| Rule | IS 2017-22 | OOS 2023+ | Verdict |
|---|---|---|---|
| 288 trials reading out soon per R&D dollar | no positions (0 months with 20 scored names; at most 14 scored) | no positions | rejected: not testable, matched names under the 20-name minimum |
| 289 no drug or device recall in 24 months | -0.1% (IR -0.03, pl 0.48) | +0.4% (IR 0.15, pl 0.61) | rejected: nothing |

Coverage: 73 covered members (SIC 28/38); 10-14 had a matched trial record and R&D at any date (never the 20 needed); 37-55 covered members had no matched recall and 10-20 had one. Reported, not judged: 289 mirror (members with a recent recall) IS -0.1%, OOS -0.9%. Correlation of 289 with low accruals -0.03, R&D 0.03, sales/price 0.19.

### Plain English
The trial calendar idea could not be tested properly: only about a dozen drug makers could be matched to the trial register by name without hand work, short of the 20 the rule needs, and the register also only shows final dates, which would flatter any result. The recall idea (no recall in two years, health-care firms only) did nothing. No pass.
