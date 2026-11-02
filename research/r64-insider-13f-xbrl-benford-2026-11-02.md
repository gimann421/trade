# Round 64: opportunistic insider buys, 13F breadth, XBRL extension share, Benford (2026-11-02)

Ideas 6, 8, 9 and 10 of the Opus idea list (`/mnt/project-files/research/opus-new-ideas-ranked-2026-11-01.md`, requested by Garret 2026-11-01) as hypotheses 278 to 281 (round 63 covers 275 to 277: 7, 11, 12). These are the ideas that need SEC bulk downloads; Garret added SEC_CONTACT on 2026-11-02 and the Form 4 insider data sets, Financial Statement Data Sets and Form 13F Data Sets all answer from the container. 277 hypotheses are counted before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of these tests was computed.** No return of any of the four rules was looked at before writing it.

## Rules (equal weight, benchmark = equal-weight scored names for quintile rules, equal-weight priced members for the basket)
- 278 `oppinsiderbuy_basket`: SEC Insider Transactions Data Sets, Form 4 and 4/A, non-derivative lines with code P (open-market purchase) where the reporting owner's relationship includes Officer or Director, value (shares x price) >= $50,000, issuer CIK of the member. A purchase is **routine** if the same owner (reporting-owner CIK) filed a P or S line (any size) at the same issuer in the same calendar month in each of the 3 prior calendar years (by transaction date); otherwise **opportunistic**. Basket: members with at least one opportunistic purchase filed (filing date) in the 180 days before the decision day. Equal weight; cash if fewer than 8 names. Data from 2013Q1 so the 3-year look-back works from 2016.
- 279 `breadth_quintile`: SEC Form 13F Data Sets. For each report quarter, the set of 13F-HR filers (original filings only, first filing per filer and period) holding the member's common shares (CUSIP, shares, no put/call). Breadth change = (holders this quarter minus holders last quarter) / (filers present in both quarters), counting only filers in both. Usable from the 46th day after quarter end. Hold the highest 20%. CUSIP-to-member map: CUSIPs whose most common issuer name among holders equals the member's conformed 10-K company name (normalised), with at least 20 holders; misses listed in the results and fixed by hand only where the name clearly changed (those fixes are listed).
- 280 `lowextension_quintile`: SEC Financial Statement Data Sets, the latest 10-K (form type 10-K only) filed before the decision day and ending within 455 days. Among distinct USD tags with no segment or co-registrant, reported for the fiscal-year-end date, the share whose tag version equals the filing's own accession number (a company extension). Hold the lowest 20%.
- 281 `benford_quintile`: same filings. All distinct (tag, date, duration, value) USD values with no segment or co-registrant and absolute value >= 10; first-digit shares; score = mean absolute deviation from Benford's expected shares. At least 200 values. Hold the lowest 20% (closest to Benford).
No variants: one rule per idea as written.

## Common setup
Round 25-62 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names (set rules: scored = priced members). Annual data: the 10-K must be filed before the decision day and its fiscal year must end within the last 455 days.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes (low accruals, R&D, sales/price); tech/health share. Correlation above 0.7 with an existing pass is the same bet.

## Multiple testing
Four rules, no variants. Total tested after this round: 281 . The bar is not loosened; with this many tests a pass is read as a lead needing the forward record, as for the earlier passes.

## Results
**Verdict: all four rejected (hypotheses 278-281, ledger ids 278-281).** Tests after this round: 281. Run 2026-11-02, `backtests/round64_tests/`. Reference rules reproduce roughly (low accruals +3.0/+3.4, R&D +4.6/+14.6, sales/price +4.6/+3.8 against +2.8/+3.2, +5.5/+15.8, +4.5/+3.3 before; small drift from refetched data).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 278 opportunistic insider buys | +3.0% (IR 0.74, pl 1.00) | +1.2% (0.29, pl 0.82) | rejected: short out of sample |
| 279 rising 13F breadth | -1.2% (-0.17, pl 0.15) | +5.0% (0.63, pl 1.00) | rejected: wrong sign in-sample |
| 280 lowest XBRL extension share | +2.1% (0.57, pl 0.98) | +1.6% (0.48, pl 0.89) | rejected: just short out of sample |
| 281 closest to Benford | +0.2% (0.08, pl 0.59) | -2.5% (-0.90, pl 0.04) | rejected |

Reported, not judged:
- Coverage: 278 scores all priced members (basket), 279 has 317-428 scored names (13F data ends with the 2026Q1 period, so the last decisions carry no breadth score), 280 321-496, 281 315-471.
- 279: my first run scored members whose CUSIP was not mapped as zero change (501 scored names); that gave IS +0.8% (pl 0.78), OOS +6.1%. I then limited scoring to members with at least 20 holders found in both quarters (the rule's mapping clause), which is the result above. Both fail. Presence of a filer in both quarters is measured as holding at least one member stock, since the reduced files keep only member lines. The CUSIP map is name-based (368 of about 500 current members); no hand fixes were made.
- Mirrors: 278 basket-less names IS -0.7%, OOS -0.3%; 279 lowest breadth gain IS 0.0%, OOS -0.6% (nothing there either); 280 highest extension share IS -2.5%, OOS 0.0%; 281 farthest from Benford IS -0.3%, OOS +0.5%.
- Correlation with low accruals / sales/price / R&D: 278 0.08 / 0.40 / -0.24; 279 0.15 / -0.48 / 0.48; 280 -0.07 / -0.38 / 0.23; 281 -0.12 / -0.08 / 0.01. Tech/health share of picks: 36%, 49%, 53%, 34%.
- 280 is the nearest miss (+2.1% and +1.6%, placebo 0.98 and 0.89) and is a tech/health-leaning, anti-sales/price tilt. It is not a lead: out-of-sample net active is under the bar and with 281 tests a lead this weak is noise-sized.

### Plain English
Companies where bosses recently bought their own stock at unusual times did a little better than average, fading after 2022. Companies that more big investors started to hold did worse before 2023 and better after, so no steady edge (the first-pass numbers are in the notes above). Companies using the plainest accounting labels did slightly better in both periods but not by enough to count. Companies whose numbers look most like the textbook digit pattern did no better, and worse recently. No pass.

