# Round 60: asset age and long-term investment holdings (2026-10-30)

Garret's standing ask (keep searching until more rules pass; coordinator re-relayed 2026-10-30, do not pause). Idea chosen by the thread. Hypotheses 268-269; 267 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of this test was computed.** Only the XBRL concept list used in rounds 25-59 was looked at.

## Where the idea comes from
Two items not used before. (1) Asset age: accumulated depreciation over gross property, plant and equipment. A young asset base means recent investment and lower near-term capital needs; an old one means catch-up spending ahead. Pre-registered direction: lowest (youngest) = buy. (2) Long-term investments over assets: cash parked in securities outside the operating business; pre-registered direction: lowest share = buy (money in operations rather than in a portfolio). Mirrors reported, not judged.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 268 `youngassets_quintile`: -(`PropertyPlantAndEquipmentAccumulatedDepreciation...` / `PropertyPlantAndEquipmentGross`) at the latest fiscal year end. The accumulated-depreciation concept used is `AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment`. Gross > 0 and ratio between 0 and 1.
- 269 `lowinvestments_quintile`: -(`LongTermInvestments` / assets); a name counts 0 if it reports the tag in any other year.
Annual data: latest 10-K filed before the decision, no older than 455 days.

## Common setup
Round 25-59 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes; tech/health share. Correlation above 0.7 with an existing pass is the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 269.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 268-269).** Tests after this round: 269. `backtests/round60_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 106 to 202 scored names (268) and 27 to 63 (269, thin).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 268 youngest PP&E (lowest accumulated depreciation share) | -2.1% (IR -0.37, pl 0.10) | +1.8% (0.30, pl 0.78) | rejected: wrong sign in-sample |
| 269 lowest long-term investments / assets | -4.0% (-0.53, pl 0.10) | +1.3% (0.15, pl 0.63) | rejected: wrong sign in-sample |

Mirrors (report only): oldest assets IS -1.5% / OOS +6.0% and most long-term investments IS +3.3% / OOS -0.2%. Both flip sign between windows, so noise. Correlation with the three passes at most 0.23 in absolute terms.

### Plain English
Companies with newer factories and equipment did not do better, and companies holding little in long-term investments did worse until 2022. Nothing held up in both periods. No pass.
