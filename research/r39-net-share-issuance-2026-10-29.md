# Round 39: net share issuance (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Idea chosen by the thread. Hypothesis 224; 223 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of this test was computed.**

## Where the idea comes from
Rounds 18 and 34 looked at buyback flows and stock pay; none measured the net change in the number of shares itself. Net share issuance is a published anomaly (Pontiff-Woodgate 2008; Daniel-Titman 2006 composite issuance) that works by firms issuing when overvalued and buying back when undervalued. It is well published, so the prior is that it has faded, but it uses a different source from every earlier test: the share count on the 10-K cover page (SEC dei EntityCommonStockSharesOutstanding, already downloaded in round 36), adjusted for stock splits with the Alpaca split table from round 33.

## Rule
- 224 `buyback_quintile`: the 20% of scored names with the largest shrink in shares outstanding between their last two 10-K cover counts (filings 300 to 430 days apart), after dividing out any split with an ex-date between the two filings. Names whose count fell by more than 50% are dropped as a likely share-class reporting change. Only the latest 10-K within 455 days of the decision is used, known from its filing date on.

## Common setup
Round 25-38 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirror (largest issuers); correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
One rule, no variants. Total tested after this round: 224.

## Results (run 2026-10-29)

**Verdict: rejected (hypothesis 224); a consistent near miss, not rescued.** Tests after this round: 224. `backtests/round39_tests/`. Check: the low-accruals, R&D and sales/price references reproduce.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 224 largest share-count shrink | +1.8% (0.33, 0.96) | +1.6% (0.36, 0.89) | rejected: net active below 2.0% in both windows, OOS placebo 0.887 |

Flag: the sign is right in both windows, so this is the closest a published issuance effect has come, but both windows are below the 2.0%/yr floor and the OOS placebo fails; the bar is not loosened. Mirror (largest issuers): -1.5% / +5.6% (issuers did best since 2023, the opposite of the theory). Correlation with sales/price 0.52, low accruals 0.25, R&D -0.15; 31% tech/health. Coverage 288 to 426 scored names.

### Plain English
- **Companies that cut their share count the most (big buybacks)** beat the average by about 1.7%/yr in both periods, below the 2% bar and not strong enough to rule out chance. Since 2023 the biggest share issuers actually did best, so the effect is not dependable.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
