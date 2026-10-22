# Round 26: cash profitability, ROA change, low capex and free cash flow (2026-10-22)

Garret said on 2026-10-22 to keep searching until more rules pass. Ideas chosen by the thread. Hypotheses 180-183; 179 were tested before this round, so the chance of a lucky pass is higher than a single test suggests. The bar below is the round 25 bar, nothing is loosened.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
- **Cash flow over assets** (Piotroski 2000; Novy-Marx-style profitability on a cash basis). Gross profit over assets was rejected in round 25 (lost 7.8%/yr from 2023), but operating cash flow is the other half of the proven accruals signal, so it is a branch off a pass.
- **Change in ROA** (Piotroski F-score component): net income over assets this year minus last year. Improving profitability, from the same filings as accruals.
- **Low capex over assets** (Titman-Wei-Xie 2004 "capital investments and stock returns"): firms that invest less than their peers earn more afterwards. Related to the rejected asset-growth test (round 25) but measures spending, not balance-sheet growth; novel here.
- **Free cash flow over assets** (operating cash flow minus capex): combines the first and third ideas into the standard cash-yield style signal.

## Common setup
Round 25 setup exactly: annual first-filed 10-K values usable only after the filing date, fiscal year ending within 455 days of the decision, current S&P 500 members, monthly decisions from 2017-01-31 filled at the close, hold the top 20% of scored names equal weight, benchmark equal weight of scored names, 5 bps primary and 10 bps stress, windows IS 2017-22 and OOS 2023+, minimum 20 scored names (`round18_tests.run_rule`).
- 180 `cfo_assets_quintile`: highest operating cash flow / assets.
- 181 `droa_quintile`: highest (net income / assets) minus the prior fiscal year's, prior year ending 335-395 days earlier.
- 182 `lowcapex_quintile`: lowest PaymentsToAcquirePropertyPlantAndEquipment / assets (names without the tag are unscored, not zero).
- 183 `fcf_assets_quintile`: highest (CFO - capex) / assets, names with both.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, selection placebo >= 0.95 (1000 random same-size baskets, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors, correlation of each rule's monthly active return with low accruals, and a one-line check on the part of the rule that is not low accruals. A pass needs a distinct signal: if the monthly active return correlates above 0.7 with low accruals it is reported as the same bet, not a new rule.

## Multiple testing
Four rules, no variants. Total tested after this round: 183.

## Results (run 2026-10-22)

**Verdict: all four rejected (hypotheses 180-183).** Tests after this round: 183. `backtests/round26_tests/`. Check: the low-accruals reference reproduces round 25 (IS +2.8%, OOS +3.2%).

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| Reference, low accruals | +2.8% (0.53, 0.99) | +3.2% (0.61, 0.98) | passes (round 25) |
| 180 high cash flow / assets | +3.2% (0.43, 0.99) | -1.1% (-0.19, 0.21) | rejected: edge gone since 2023 |
| 181 rise in ROA | -0.6% (-0.11, 0.36) | +5.4% (0.97, 1.00) | rejected: one era only |
| 182 low capex / assets | +0.5% (0.09, 0.58) | +1.3% (0.21, 0.78) | rejected: no edge |
| 183 free cash flow / assets | +3.0% (0.45, 0.98) | -2.5% (-0.45, 0.06) | rejected: edge gone since 2023 |

Mirrors (report only): low cash flow +4.2% OOS and -1.9% IS, so cash-flow rules flip sign between eras. Correlation of monthly active return with low accruals: 0.19, 0.15, 0.03, 0.18, so none of these was a repeat of the accruals bet. Capex is tagged for 375 of 503 members (financials mostly missing).

### Plain English
- **Cash-rich companies** (strong operating cash flow for their size) beat the average in 2017-22 and lagged since 2023. Same for free cash flow. A rule that works in only one period does not pass.
- **Companies whose profit margin on assets is rising** did well since 2023 and nothing before, again one era.
- **Companies that spend little on equipment and plants** showed no reliable edge.
- Low accruals stays the only fundamentals rule that works in both periods; these checks suggest its edge is the gap between profit and cash, not cash itself.
