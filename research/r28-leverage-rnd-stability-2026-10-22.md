# Round 28: low leverage, deleveraging, R&D intensity and stable earnings (2026-10-22)

Garret said on 2026-10-22 to keep searching until more rules pass. Ideas chosen by the thread. Hypotheses 187-190; 186 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Low accruals is the one pass and it came from annual SEC filings, an area where price-based ideas keep failing. Four more filing-based families, each with its own literature and none tested here:
- **Low leverage** (Bhandari 1988 leverage and returns; Penman-Richardson-Tuna 2007): total liabilities over assets, lowest quintile.
- **Falling leverage** (Lewellen-Nagel-style financing; Spiess-Affleck-Graves net financing): the lowest change in liabilities over assets year over year, i.e. firms paying down rather than taking on obligations.
- **R&D intensity** (Chan-Lakonishok-Sougiannis 2001; Lev-Sarath-Sougiannis): highest R&D expense over assets, among names that report R&D.
- **Stable earnings** (Huang 2009; Dichev-Tang earnings volatility): lowest standard deviation of net income over assets across the last 4-5 fiscal years (at least 4 valid years).

## Common setup
Round 25-27 setup exactly (annual first-filed 10-K values usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names). Prior year = fiscal year end 335-395 days earlier.
- 187 `lowlev_quintile`: lowest Liabilities / Assets.
- 188 `deleverage_quintile`: lowest (Liabilities/Assets) minus last year's.
- 189 `rnd_quintile`: highest ResearchAndDevelopmentExpense / Assets among names reporting it.
- 190 `stableroa_quintile`: lowest standard deviation of NetIncomeLoss / Assets over up to the last 5 fiscal years, at least 4.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors and correlation of monthly active return with low accruals (above 0.7 means the same bet, not a new rule).

## Multiple testing
Four rules, no variants. Total tested after this round: 190.

## Results (run 2026-10-22)

**Verdict: one of four clears the pre-registered bar, `rnd_quintile` (hypothesis 189), with large flags below. The other three are rejected (187, 188, 190).** Tests after this round: 190. `backtests/round28_tests/`. Check: the low-accruals reference reproduces (IS +2.8%, OOS +3.2%).

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| Reference, low accruals | +2.8% (0.51, 0.99) | +3.2% (0.60, 0.97) | passes (round 25) |
| 187 low liabilities / assets | +0.2% (0.03, 0.56) | +2.1% (0.33, 0.85) | rejected: nothing in IS |
| 188 falling liabilities / assets | -0.5% (-0.11, 0.38) | -3.6% (-0.76, 0.01) | rejected |
| **189 highest R&D / assets** | **+5.5% (0.52, 1.00)** | **+15.8% (1.43, 1.00)** | **passes the bar** (+5.4% / +15.7% at 10 bps) |
| 190 lowest earnings variability | -1.2% (-0.19, 0.09) | -3.3% (-0.54, 0.01) | rejected (mirror, high variability, +2.5% / +7.2%: report only) |

Correlation of 189's monthly active return with low accruals: 0.36 (not the same bet). Mirror (lowest R&D quintile): -1.8% / -8.3%.

### Robustness (written after the pass was seen: diagnostics, not new hypotheses; `research/round28_robust.py`)
| Variant | IS | OOS |
|---|---|---|
| quintile (the rule) | +5.5% | +15.8% |
| decile | +7.9% | +13.0% |
| tercile | +5.2% | +10.2% |
| within the same 2-digit industry (top 20% of each) | +6.8% (IR 0.76) | +12.8% (IR 1.39) |
| excluding tech, health and chemicals (SIC 28, 35-38, 73) | +0.6% (placebo 0.55) | +11.3% (placebo 0.98) |
| against all priced members instead of R&D reporters | +9.7% | +20.8% |

Active return by calendar year: 2017 -1.5%, 2018 +10.8%, 2019 +10.8%, 2020 +13.4%, 2021 +12.6%, 2022 -13.4%, 2023 +18.8%, 2024 +5.0%, 2025 +12.5%, 2026 (to date) +26.4%; 8 of 10 years positive.

### Flags (why this is not a clean pass)
1. **It is nearly a tech and health-care bet.** 97-100% of the picks are SIC 28, 35-38 or 73 names. Without them the 2017-22 edge is gone (+0.6%). Within an industry the edge holds (+6.8% / +12.8%), which argues it is more than a sector call, but the +15.8% since 2023 coincides with the AI rally.
2. **Current-member bias is worst here.** The universe is today's S&P 500 members; heavy R&D spenders that became large and were added to the index are exactly the winners, and R&D spenders that fell out are missing. Low accruals has the same limit but less exposure to it. The Sharadar-era recheck (2000-2015, delisted names included) matters most for this rule.
3. **190 tests were run**; the placebo (1.00) only compares against random baskets of R&D names, so it says nothing about the sector concentration or the member bias.
4. Only 220 of 503 members report the R&D tag, and the 2022 drawdown was -13.4%.
5. The gain is far above anything else found (OOS +15.8%): size alone is a reason to check it on older data before trusting it.

### Plain English
- **Companies that spend the most on research and development** (relative to their size) beat the average of that group by about 5% a year in 2017-22 and about 16% a year since 2023, in 8 of 10 years. It held up with 10 bps costs, with a wider or narrower basket, and when comparing only within the same industry.
- **But** almost all of the picks are technology and health-care companies, and the edge disappears in 2017-22 if you drop those. The test also only covers companies that are in the S&P 500 today, which flatters fast-growing research-heavy firms.
- **Low debt, falling debt and steady earnings** did not work.
- Honest read: it clears the bar we set, but it is the weakest kind of pass, because the main risks are a sector bet and survivorship rather than pure luck. It should be rechecked on older data before any money follows it.
