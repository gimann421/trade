# Round 49: buybacks, shareholder yield, asset-light balance sheets (2026-10-30)

Garret's standing ask (keep searching until more rules pass; relayed again by the coordinator 2026-10-30 with an explicit instruction not to pause). Idea chosen by the thread. Hypotheses 244-246; 243 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.** Before writing it, only the list of XBRL concepts already used in rounds 25-41 was looked at. (An insider-transaction idea with buy/sell direction was dropped first: the only source, the Alpha Vantage connector, allows 25 requests a day on the free key, so 503 tickers are not reachable. Never run, not counted.)

## Where the idea comes from
Net share shrink was a near miss (round 39: IS +1.8%, OOS +1.6%) but measured the share count, which is also moved by stock compensation and splits. The cash actually spent on repurchases and dividends (Boudoukh et al. 2007 on net payout yield; Peyer-Vermaelen 2009 on buyback announcements) was never tested directly. Asset-light balance sheets are a separate dimension: lower fixed-asset intensity is the mirror of the capital-intensity and investment effects (Titman-Wei-Xie 2004; round 28 lowcapex rejected), measured on the balance sheet instead of the cash flow. SEC XBRL (`PaymentsForRepurchaseOfCommonStock`, `PaymentsOfDividends` or `PaymentsOfDividendsCommonStock`, `PropertyPlantAndEquipmentNet`), first-filed 10-K values, `data/round49/` (git-ignored). Market value as in round 36.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 244 `buybackyield_quintile`: repurchase cash over the year / market value at the decision date. Highest 20%. Scored only if the repurchase value is reported for the latest annual period.
- 245 `shareholderyield_quintile`: (repurchases + dividends paid) / market value; a missing dividend value counts as 0. Highest 20%.
- 246 `assetlight_quintile`: net PP&E / assets, lowest 20%.
Annual data: latest 10-K available before the decision (filed date), no older than 455 days. Mirrors (lowest 20% for 244 and 245, highest for 246) reported, not judged.

## Common setup
Round 25-48 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price; tech/health share of picks. A correlation above 0.7 with an existing pass counts as the same bet.

## Multiple testing
Three rules, no variants. Total tested after this round: 246.

## Results (run 2026-10-30)

**Verdict: all three rejected (hypotheses 244-246); 244 is a near miss that fails on one line.** Tests after this round: 246. `backtests/round49_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3). Coverage 116 to 273 scored names per month for 244-245 (repurchase value reported), 126 to 240 for 246.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 244 highest buyback yield | +3.5% (IR 0.41, pl 0.98) | +2.7% (0.45, pl **0.935**) | rejected: OOS placebo 0.935 < 0.95; everything else clears, including 10 bps (+3.4% / +2.7%) |
| 245 highest shareholder yield | +3.4% (0.35, pl 0.98) | +1.7% (0.24, pl 0.82) | rejected: OOS below 2.0%, IR 0.24, placebo 0.82 |
| 246 lowest PP&E / assets | -0.5% (-0.06, pl 0.27) | +0.6% (0.09, pl 0.63) | rejected |

Correlations: 244 with sales/price **0.69** (just under the 0.7 same-bet line; 245 is 0.75), with low accruals 0.12, with R&D -0.28; tech/health share 28%. So even a lucky pass would have been mostly the sales/price bet. Mirror of 244 (lowest buyback yield, report only): IS -3.0%, OOS +2.8%: the effect exists in-sample and reverses in the lowest group out-of-sample, the usual era instability.

### Plain English
Companies that spend the most on buying back their own shares did 3.5% and 2.7% a year better than average, after costs. That nearly cleared the bar but missed the chance-odds check in the recent period (0.935 against the required 0.95), and it overlaps heavily with the sales/price rule (correlation 0.69), so it is largely the same bet and not a new one. Dividends added nothing. Asset-light companies did no better.
