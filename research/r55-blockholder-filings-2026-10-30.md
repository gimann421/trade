# Round 55: block-holder filings, Schedule 13D and 13G (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 257-258; 256 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the filing counts by form and year (46,607 Schedule 13D/13G rows, 2015-10 to 2026-10, 503 current members) and the number of names filed on in one year were looked at. No returns were examined.

## Where the idea comes from
Anyone who crosses 5% of a listed company must file a Schedule 13D (an activist or controlling intent) or 13G (a passive holder, mostly large asset managers). Activist stakes are followed by abnormal returns (Brav-Jiang-Partnoy-Thomas 2008 for hedge-fund activism); a new passive 5% holder is institutional demand arriving. Round 44 used only Form 4, Form 144 and 8-K counts; blockholder filings were not used, and the direction of the filing is clear from its form type (no buy/sell ambiguity as with Form 4). Source: SEC submissions API (`data/round55/filings.csv`, `research/round55_data.py`), current S&P 500 members only. The old names (`SC 13D`, `SC 13G`) and new names (`SCHEDULE 13D`, `SCHEDULE 13G`, from December 2024) are treated as the same form; an `/A` suffix is an amendment.

Regime caveat, disclosed in advance: the SEC changed the Schedule 13G rules from 2024 (earlier deadlines, quarterly amendments), and filing counts roughly doubled in 2024-26 (initial 13D/G filings per year: 700 to 1,000 until 2023, 1,400 to 2,200 after). To avoid a threshold that drifts with the rule change, rule 258 uses a cross-sectional cut each month, not a fixed count.

## Rules (equal weight, benchmark equal-weight priced members; set rules, not top-20% rules)
- 257 `activist13d_basket`: names with at least one Schedule 13D or 13D/A filed in the trailing 365 days (about 15% of names). Cash if fewer than 8 names.
- 258 `newholder13g_basket`: names whose number of initial Schedule 13G filings (no amendments) in the trailing 365 days is above the 80th percentile of that count across priced members on the decision date (if that percentile is 0, any name with at least one). Cash if fewer than 8 names.
Mirrors (names not picked) reported, not judged. A filing counts from the day it is filed.

## Common setup
Round 25-54 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 258.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 257-258); 257 is a half-pass.** Tests after this round: 258. `backtests/round55_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). All 501 to 505 priced members are scored every month (a name with no filing counts as 0).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 257 any 13D / 13D-A in the last 365 days | +2.6% (IR 0.59, pl 0.98, 10 bps +2.6%) | +1.0% (0.25, pl 0.71, 10 bps +0.9%) | rejected: OOS below 2.0%, IR 0.25, placebo 0.71 |
| 258 initial 13G count above the 80th percentile | -0.4% (-0.07, pl 0.40) | +2.6% (0.63, pl 0.94) | rejected: in-sample negative |

257 clears the bar in-sample (+2.6%, IR 0.59, placebo 0.98) but not since 2023 (+1.0%). Activist-stake names are about 15% of the index. 258 is the reverse: nothing before 2023, +2.6% since (placebo 0.94), the usual era flip; it also coincides with the 2024 change in Schedule 13G rules that roughly doubled filing counts, so its out-of-sample strength cannot be told apart from the rule change. Mirrors (report only): non-13D names -0.4% / -0.1%, low-13G-count names -0.0% / -0.5%. Correlations with the passes: 257 with low accruals 0.29, sales/price 0.36, R&D -0.23; 258 with low accruals 0.03, sales/price 0.41, R&D -0.28; tech/health share 30% / 28%.

### Plain English
Companies where an activist investor took a big stake did a little better than average before 2023 (about 2.6% a year) and only a little better since (1.0%), too weak to count and not reliable after costs. Companies that recently gained a new large passive holder did nothing before 2023 and better since, which lines up with a change in how those filings are made, so we cannot trust it. No new rule.
