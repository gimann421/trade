# Round 40: affiliate (insider and large-holder) ownership (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Idea chosen by the thread. Hypothesis 225; 224 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.**

## Where the idea comes from
A new source: the 10-K cover page reports the aggregate market value held by non-affiliates (SEC dei EntityPublicFloat) as of the last day of the second fiscal quarter. Affiliates are officers, directors and holders of 10% or more, so one minus the float over the total market value is a proxy for how much of the company is held by insiders and large holders. Closely held firms are linked to different governance and incentives (Morck-Shleifer-Vishny 1988; Demsetz-Lehn 1985); a public-float effect on returns has been argued by Brav-Constantinides-Geczy-style holder studies, but the signal has not been used in the earlier rounds, whose ideas came from the financial statements and prices. Form 4 data (www.sec.gov) stays unreachable, and this field is the one insider-related quantity available from the SEC data API.

## Rule
- 225 `affiliate_quintile`: the 20% of scored names with the highest affiliate share = 1 - public float / (cover-page shares outstanding in the 10-K x unadjusted close on the float date). Values outside -0.2 to 1.0 are dropped as share-class or reporting mismatches. The latest 10-K within 455 days of the decision is used, known from its filing date on. Direction: highest. The mirror (lowest affiliate share, widely held) is reported, not judged.

## Common setup
Round 25-39 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names. Share count is the filing-date cover count, not the float-date count, so the ratio is noisy; names with heavy buybacks or issuance between the two dates are mismeasured.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirror; correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
One rule, no variants. Total tested after this round: 225.

## Results (run 2026-10-29)

**Verdict: rejected (hypothesis 225).** Tests after this round: 225. `backtests/round40_tests/`. Check: the low-accruals, R&D and sales/price references reproduce. Coverage 306 to 433 scored names (33 in the first month, so 2017 is thin).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 225 highest affiliate share | +1.1% (0.24, 0.82) | +4.1% (0.83, 1.00) | rejected: IS +1.1%, IR 0.24, placebo 0.823 |

Mirror (widely held, report only): IS +1.0%, OOS -0.2%. Correlation with R&D 0.66 (43% tech/health: founder-held tech names), low accruals 0.49, sales/price -0.36.

### Plain English
- **Companies where insiders and big holders own the most** did well since 2023 (+4.1%/yr) but only +1.1%/yr in 2017-22, and they are largely the same tech names as the R&D rule.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
