# Round 30: cash holdings, operating profitability, low tax rate and low interest burden (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 195-198; 194 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Both passes (low accruals, R&D intensity) came from annual SEC filings, where price-based ideas keep failing. Four more filing families, none tested here:
- **Cash holdings over assets** (Palazzo 2012 "Cash holdings, risk, and expected returns"): firms holding more cash relative to assets earn more later (a risk-compensation story).
- **Operating profitability over assets** (Fama-French 2015 RMW uses operating profit; gross profit over assets failed in round 25, and operating income differs by including overhead and R&D expense).
- **Low effective tax rate** (Abarbanell-Bushee style tax signals; Lev-Nissim 2004 "taxable income, future earnings, and equity values"): income tax expense over pre-tax income (net income plus tax), lowest quintile, among names with positive pre-tax income and a rate between 0 and 60%.
- **Low interest burden** (Penman-Richardson-Tuna 2007 financing component): interest expense over total assets, lowest quintile, among names reporting interest expense (a tag-presence limit: firms with none are unscored).

## Common setup
Round 25-29 setup exactly (annual first-filed 10-K values usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names).
- 195 `cash_quintile`: highest CashAndCashEquivalentsAtCarryingValue / assets.
- 196 `opprofit_quintile`: highest OperatingIncomeLoss / assets.
- 197 `lowtax_quintile`: lowest IncomeTaxExpenseBenefit / (NetIncomeLoss + IncomeTaxExpenseBenefit), among names with NetIncomeLoss + tax > 0 and a rate between 0 and 0.6.
- 198 `lowinterest_quintile`: lowest InterestExpense / assets, among names reporting InterestExpense > 0.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation of the monthly active return with low accruals and with R&D intensity (above 0.7 means the same bet, not a new rule); the tech/health share of the picks.

## Multiple testing
Four rules, no variants. Total tested after this round: 198.

## Results (run 2026-10-29)

Note on the run: the first run scored the tax-rate rule on net income taken from the new fact file, which does not contain it, so `lowtax_quintile` scored zero names. That was a code bug found from the empty coverage column before any result of the rule could be read; it was fixed (net income now comes from the round 25 annual table) and the whole script was re-run. The ledger holds evidence rows from both runs for 197; the second is the one that counts.

**Verdict: `cash_quintile` (hypothesis 195) clears the numeric bar, but the pre-registered rule makes it the same bet as R&D intensity (correlation 0.72 > 0.7), so it is NOT counted as a new rule. 196, 197 and 198 are rejected.** Tests after this round: 198. `backtests/round30_tests/`. Check: the low-accruals and R&D references reproduce.

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| **195 highest cash / assets** | **+3.3% (0.44, 1.00)** | **+5.5% (0.69, 1.00)** | clears the bar; same bet as R&D (corr 0.72) |
| 196 highest operating income / assets | +2.3% (0.40, 0.96) | -0.4% (-0.09, 0.41) | rejected |
| 197 lowest effective tax rate | -0.1% (-0.02, 0.42) | +4.5% (0.86, 1.00) | rejected: one era only |
| 198 lowest interest / assets | -1.4% (-0.28, 0.11) | +6.1% (1.05, 1.00) | rejected: one era only |

Mirrors (report only): low cash -3.1% / -7.8%; high interest +0.3% / +3.5%. Correlation with low accruals: 0.39, -0.01, 0.17, 0.10. Correlation with R&D intensity: 0.72, 0.46, 0.61, 0.35. Mean tech/health share of picks: 61%, 53%, 53%, 34%.

### Robustness of 195 (written after seeing it; `research/round30_robust.py`)
| Variant | IS | OOS |
|---|---|---|
| quintile (the rule) | +3.3% | +5.5% |
| decile | +3.2% (placebo 0.94) | +6.9% |
| tercile | +2.6% | +5.1% |
| excluding tech, health and chemicals | +0.7% | +2.8% |
| within the same 2-digit industry | +1.8% | +1.8% |
| only names with no R&D reported | +0.1% | +4.7% |

Active return by calendar year: 2017 +6.3%, 2018 +3.7%, 2019 +6.9%, 2020 +12.3%, 2021 -0.8%, 2022 -8.7%, 2023 +9.6%, 2024 +1.7%, 2025 +3.1%, 2026 +5.8%; 8 of 10 positive.

### Reading
Cash-rich companies are largely the same tech and health-care names that spend on R&D. Inside an industry the edge is +1.8% in both eras (below the 2.0% bar), outside tech and health it is +0.7% in 2017-22, and among names with no R&D it is +0.1% in 2017-22. So there is a real but modest cash effect that mostly duplicates R&D intensity and sector. Nothing is proposed for a shadow record; the R&D record already covers this bet.

### Plain English
- **Companies holding a lot of cash for their size** beat the average of that group in both periods (+3.3%/yr, then +5.5%/yr). But they are mostly the same technology and health-care companies as the R&D rule, so it is the same bet seen from another angle, not a second independent rule.
- **Highest operating profit** was fine in 2017-22 and flat since. **Low tax rate** and **low interest costs** each worked in only one period.
- Still just two independent rules that clear the bar: low accruals and R&D intensity.
