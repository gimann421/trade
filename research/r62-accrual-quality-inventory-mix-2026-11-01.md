# Round 62: accrual quality and inventory mix (2026-11-01)

Second round of the Opus idea list (`/mnt/project-files/research/opus-new-ideas-ranked-2026-11-01.md`, requested by Garret 2026-11-01): ideas 4 and 5 as hypotheses 273 and 274. 272 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of this test was computed.** No return of either rule was looked at before writing it.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 273 `accrualquality_quintile` (Dechow-Dichev): for each fiscal year y (labelled by the calendar year of its fiscal year end) and each 2-digit SIC group with at least 10 firms, regress accruals_y = (net income - operating cash flow)_y / assets_y on CFO_{y-1}, CFO_y and CFO_{y+1}, each over assets_y, by ordinary least squares with intercept, using only firms whose y+1 10-K was filed before the decision day (so year y becomes usable only when the y+1 10-K is out). Accrual quality = standard deviation of a firm's residuals over its latest 5 usable years (at least 3). The latest usable year's y+1 10-K must end within the last 455 days. Hold the lowest 20%. First-filed 10-K values; consecutive fiscal years are those whose year ends are 335 to 395 days apart.
- 274 `rawshare_quintile`: Raw = first available of `InventoryRawMaterialsNetOfReserves`, `InventoryRawMaterials`, `InventoryRawMaterialsAndSuppliesNetOfReserves`, `InventoryRawMaterialsAndSupplies`; WIP = first available of `InventoryWorkInProcessNetOfReserves`, `InventoryWorkInProcess` (0 if neither); FG = first available of `InventoryFinishedGoodsNetOfReserves`, `InventoryFinishedGoods`. Share = Raw / (Raw + WIP + FG) at fiscal year end. Score = share this year minus share last year (year ends 335 to 395 days apart); raw and finished goods must both be reported in both years. Hold the highest 20%. Coverage will be only manufacturers (about 45% of members).
Annual data: latest 10-K filed before the decision, fiscal year ending within the last 455 days.

## Common setup
Round 25-61 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes (the key check for 273, the closest branch of the low accruals pass); tech/health share. Correlation above 0.7 with an existing pass is the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 274.

## Results (run 2026-11-01)

**Verdict: both rejected (hypotheses 273-274).** Tests after this round: 274. `backtests/round62_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 74-246 scored names (273), 65-152 (274).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 273 lowest accrual-residual noise | -2.6% (IR -0.35, pl 0.03) | -1.9% (-0.25, pl 0.19) | rejected: wrong sign in both |
| 274 largest rise in raw-materials share | +4.3% (0.65, pl 0.98) | +1.5% (0.21, pl 0.68) | rejected: passes in-sample, short out of sample |

Reported, not judged:
- 273 mirror (noisiest accruals) IS +1.6% (pl 0.85), OOS +6.8% (IR 1.01, pl 1.00): short of the bar in-sample and the wrong direction against the pre-registered idea; correlation of 273 with sales/price is 0.60 and with R&D -0.61 (11% tech/health picks), with low accruals -0.25. Not a pass and not a lead.
- 274 mirror (largest fall in raw share) IS -1.5%, OOS +8.3%: a sign flip.
- 274 picks are 82% tech/health names; correlation with low accruals 0.42, R&D 0.35, sales/price 0.02.

### Plain English
Companies with the most predictable accruals did worse than average in both periods. Companies stocking up on raw materials relative to finished goods did well until 2022 and then faded, so that one is not steady enough to count. No pass.
