# Round 44: insider and officer filing activity (2026-10-29)

Garret's standing ask (keep searching until more rules pass; relayed by the coordinator 2026-10-29, thread free to pick its direction). Ideas chosen by the thread. Hypotheses 233-235; 232 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
A source none of the earlier rounds used. Round 35 dropped Form 4 insider data because www.sec.gov is blocked, but the SEC submissions API on data.sec.gov (reachable) lists every filing a company's insiders and the company itself make: form type, filing date and, for 8-Ks, the item codes. Direction and size of insider trades are in the filing bodies (not reachable), so only filing activity and event types are used. Everything uses filings dated strictly before the decision day. Current S&P 500 members only.
- **233 `lessselling_quintile`, fewer insider sale notices** (Form 144 is the notice a holder of restricted or control stock files before selling; Seyhun 1986 and Lakonishok-Lee 2001 on insider trading signals): among names with at least 6 Form 144 filings in the 360 days before the last 180 days, the 20% with the lowest ratio of Form 144 filings in the last 180 days to the average 180-day count of the prior 360 days. Direction: lowest ratio (insiders selling less than usual).
- **234 `stablemgmt_quintile`, stable officers and directors** (8-K item 5.02 reports departures, appointments and compensation changes of officers and directors; Warner-Watts-Wruck 1988, Huson-Malatesta-Parrino 2004 on management turnover): the 20% with the fewest 8-K filings that carry item 5.02 in the trailing 365 days. Direction: fewest.
- **235 `quiet8k_quintile`, few material events** (8-K count as event flow): the 20% with the fewest 8-K filings of any kind in the trailing 365 days. Direction: fewest.

For 234 and 235 a name must have at least 2 8-K filings in the whole file to be scored (excludes data gaps). Counts are not size-adjusted; the correlation with size is reported through the other references.

## Common setup
Round 25-43 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Three rules, no variants. Total tested after this round: 235.

## Results (run 2026-10-29)

**Verdict: all three rejected (hypotheses 233-235).** Tests after this round: 235. `backtests/round44_tests/`. Check: the low-accruals, R&D and sales/price references reproduce. Data: 484,333 filings (Form 4, Form 144, 8-K, 10-K/A) for 500 current members from 2015-10 on; no ticker failed. Form 4 counts are even across years (about 34,000 per year), so the history is complete.

**A defect found after the run, disclosed:** Form 144 filings only exist on EDGAR as electronic filings from April 2023 (earlier ones were paper), so rule 233 has no usable data before mid-2024 (the prior-360-day rate needs at least 6 filings) and shows 0 rebalances in 2017-22. It cannot be judged in the in-sample window at all; it is recorded as rejected because the out-of-sample window fails on its own (+0.4%, IR 0.07, placebo 0.585). It was pre-registered without checking Form 144's start date.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 233 lower Form 144 filing rate | no data (0 rebalances) | +0.4% (0.07, 0.58) | rejected: OOS fails, IS untestable |
| 234 fewest 8-Ks with item 5.02 | +1.0% (0.34, 0.90) | -1.2% (-0.46, 0.22) | rejected |
| 235 fewest 8-Ks | -0.9% (-0.26, 0.22) | -0.0% (-0.01, 0.54) | rejected |

Mirrors (report only): 233 highest rate OOS +2.5% (0.37, 0.89); 234 most 5.02 items +0.3% / -0.4%; 235 most 8-Ks -2.5% / -0.0%. Correlation with low accruals 0.03, 0.17, 0.04; with sales/price 0.40, 0.21, -0.45; with R&D -0.46, -0.08, 0.33.

### Plain English
- **Insider selling notices, management turnover and general 8-K event flow** carried no return signal. This is the first test using insider-filing data, and it is only filing counts: whether insiders bought or sold is inside the filings and is not available here, so a proper insider-trading test is still not possible.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
