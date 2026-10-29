# Round 29: sales and admin spending, advertising, R&D growth and low goodwill (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 191-194; 190 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
R&D intensity (round 28, the second pass) is an "intangible investment" signal. Three neighbours and one contrast:
- **Selling, general and administrative spending over assets** (Eisfeldt-Papanikolaou 2013, "organizational capital"): firms that spend more on the organization earn more later.
- **Advertising spending over assets** (Chan-Lakonishok-Sougiannis 2001; Grullon-Kanatas-Weston 2004 brand and visibility): another intangible investment, sparse tag.
- **R&D growth** (Eberhart-Maxwell-Siddique 2004 "unexpected R&D increases"): the rise in R&D over assets year over year, among names reporting R&D in both years.
- **Low goodwill over assets** (Li-Sloan 2017 goodwill impairment): firms with a smaller share of assets in goodwill face less impairment risk and are less acquisition-driven.

## Common setup
Round 25-28 setup exactly (annual first-filed 10-K values usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names). Prior year = fiscal year end 335-395 days earlier.
- 191 `sga_quintile`: highest SG&A expense / assets.
- 192 `adv_quintile`: highest AdvertisingExpense / assets among names reporting it (a minimum of 20 scored names applies, so it may often hold cash early).
- 193 `drnd_quintile`: highest (R&D/assets) minus last year's, among names with R&D in both years.
- 194 `lowgoodwill_quintile`: lowest Goodwill / assets (names without a Goodwill tag count as zero goodwill only if they report Assets and Goodwill appears for any year; otherwise unscored).

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation of the monthly active return with low accruals and with R&D intensity (above 0.7 means the same bet, not a new rule); and for any pass, the tech/health share of the picks and an ex-tech/health variant, since round 28's pass was mostly a sector bet.

## Multiple testing
Four rules, no variants. Total tested after this round: 194.

## Results (run 2026-10-29)

**Verdict: all four rejected (hypotheses 191-194).** Tests after this round: 194. `backtests/round29_tests/`. Check: the low-accruals and R&D references reproduce (accruals IS +2.8% / OOS +3.2%; R&D IS +5.5% / OOS +15.8%).

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 191 high SG&A / assets | +2.1% (0.33, 0.95) | -8.0% (-1.10, 0.00) | rejected: reversed since 2023 |
| 192 high advertising / assets | -2.0% (-0.33, 0.17) | -7.6% (-1.09, 0.01) | rejected: loses in both |
| 193 rise in R&D / assets | +1.4% (0.23, 0.77) | +8.5% (1.21, 1.00) | rejected: IS below the bar |
| 194 low goodwill / assets | +1.4% (0.27, 0.89) | +2.4% (0.54, 0.92) | rejected: short of the bar in both |

Mirrors (report only): low SG&A -0.5% IS / +9.3% OOS, low advertising +2.6% / +8.8%: one-era patterns. Correlation with low accruals: -0.24, -0.10, 0.28, 0.14. Correlation with R&D intensity: -0.21, -0.24, 0.56, -0.26 (193 is the closest relative at 0.56, with 91% tech/health picks). Mean tech/health share of picks: 26%, 38%, 91%, 13%. Coverage: advertising 145 and R&D change 182 of 503 members at the end.

### Plain English
- **Companies that spend heavily on sales and administration** (and on advertising) were fine or flat in 2017-22 and lost a lot since 2023 (8% a year behind), so neither lasts.
- **Companies whose R&D spending is rising** did very well since 2023 (+8.5%/yr) but only barely in 2017-22, and it is mostly the same tech and health-care names as the R&D intensity rule, so it adds no new information.
- **Companies with little goodwill** (little value from past acquisitions) came close but fell short in both periods.
- No second pass here. R&D intensity and low accruals remain the only two rules that clear the bar.
