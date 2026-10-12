# Drawdown-reducing trend filters for SPY and QQQ (trend-analyst, 2026-10-12)

Three proposals. Before writing them I checked the ledger (`memory/ledger.db`). No hypothesis has status `rejected`. Hypothesis 1 (SMA 50/200 crossover, status `testing`) is not re-proposed. On SPY over 2016-2026 it had a Sharpe of 0.76 against 0.90 for buy-and-hold. Its max drawdown was -33.8%, the same as buy-and-hold, because the 50/200 cross came too late in the fast 2020 crash. On QQQ the evidence was inconclusive: Sharpe 0.98 vs 0.95, max drawdown -28.6% vs -35.0%. Each idea below tries to fix the slow exit in a different way: by volatility, by shorter momentum lookbacks, or by a price-channel exit.

**Shared constraints for every idea:**
- Daily bars only, from `data/SPY_1Day.csv` and `data/QQQ_1Day.csv` (2016-01-04 to 2026-10-09).
- Each symbol is tested on its own; `generate_signals(bars)` sees only that symbol's bars.
- Weights stay in [0, 1], with no shorting and no leverage.
- Orders fill at the signal day's close, as `core/backtest.py` assumes.
- Costs are 5 bps per unit of turnover.

**Shared kill rule (decided before any backtest):**
- Evaluate each symbol separately on two windows: in-sample 2016-01-01..2022-12-31 and out-of-sample 2023-01-01..end of data.
- The idea is **rejected** if, on either window for either symbol, its Sharpe after 5 bps costs is below buy-and-hold's.
- It is also **rejected** if its max drawdown is not at least 5 percentage points shallower than buy-and-hold's on that window (for example, buy-and-hold -33.8% means the strategy must be -28.8% or better).
- It is **supported** only if it passes on both windows for both SPY and QQQ.

**Warm-up:** indicators are computed on the full history, and metrics are sliced by window. The first in-sample year is partly warm-up for the 252-day lookback (idea 2). During warm-up the weight is 0, which counts against the strategy.

**What the out-of-sample window contains:** the 2023-01-01 onward window has the sharp April 2025 sell-off, so it does test drawdown control. If an out-of-sample drawdown of buy-and-hold turns out to be too shallow for the 5-point margin to mean anything, the idea still fails on the stated rule. The rule will not be relaxed after the fact.

---

## Idea A: Volatility-targeted exposure

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 2
- **Strategy file:** `strategies/vol_target_v1.py`

### Hypothesis
Holding SPY/QQQ at weight `min(1, 0.15 / annualized 20-day realized close-to-close volatility)`, recomputed daily, beats buy-and-hold on Sharpe and cuts max drawdown by at least 5 points after 5 bps costs. This must hold in both 2016-2022 and 2023-onward.

### Why it might work
- Volatility clusters, and it rises when prices fall (the leverage effect).
- Realized volatility jumps within days of a crash starting. In late February 2020 it did so weeks before a 50/200 SMA cross could happen.
- Cutting exposure when volatility is high gives up little return, because high-volatility periods have had poor return per unit of risk.
- Who is on the other side: constant-allocation holders and buy-the-dip traders who keep full exposure while risk rises.
- Why the edge may persist: many investors are bound by mandates to stay fully invested, so they cannot do this themselves.

### Market conditions it needs
- Drawdowns that come with a volatility spike, as in 2018 Q4, 2020, 2022 and April 2025.
- Calm uptrends where realized volatility stays below about 15%, so the weight stays near 1. QQQ's usual volatility is higher, so expect it to be underweight more often.

### How it could fail
- Kill threshold: Sharpe below buy-and-hold on either window, or max drawdown not at least 5 points better than buy-and-hold on either window, for either symbol (5 bps costs).
- Likely ways to fail:
  - A "V" recovery after a spike, where volatility stays high while price rebounds.
  - A slow, low-volatility grind down.
  - Persistent underexposure on QQQ that costs too much return.

### Test plan
- Symbols: SPY and QQQ, each tested separately.
- Windows: 2016-01-01..2022-12-31 and 2023-01-01..2026-10-09.
- Costs: 5 bps.
- Benchmark: buy-and-hold on the same symbol.
- Report: Sharpe, max drawdown, CAGR and average exposure for each window.
- Fixed parameters: 15% target and 20-day lookback. No parameter sweep.

### Results

**Verdict: rejected** (round 1, 2026-10-12; rule fixed before testing, scored by `research/round1_verdicts.py`). Strategy: `strategies/vol_target_v1.py`.

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Ret per exposure day (strat / B&H mean) | Exposure | Entries | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|
| SPY IS | 0.85 / 0.68 | -19.0% / -33.8% | 10.4% / 11.5% | 0.043% / 0.050% | 86% | 1 | supports: passes kill threshold | [SPY_2016-01-04_2022-12-30_20261012T032100Z.json](../backtests/vol_target_v1/SPY_2016-01-04_2022-12-30_20261012T032100Z.json) |
| SPY OOS | 1.42 / 1.43 | -14.8% / -18.8% | 19.0% / 22.4% | 0.072% / 0.085% | 95% | 1 | contradicts: Sharpe 1.42 < buy&hold 1.43; MaxDD -14.8% not 5pts better than -18.8% | [SPY_2023-01-03_2026-10-09_20261012T032100Z.json](../backtests/vol_target_v1/SPY_2023-01-03_2026-10-09_20261012T032100Z.json) |
| QQQ IS | 0.93 / 0.70 | -21.4% / -35.0% | 13.0% / 14.5% | 0.053% / 0.065% | 78% | 1 | supports: passes kill threshold | [QQQ_2016-01-04_2022-12-30_20261012T032100Z.json](../backtests/vol_target_v1/QQQ_2016-01-04_2022-12-30_20261012T032100Z.json) |
| QQQ OOS | 1.48 / 1.51 | -16.3% / -22.8% | 23.9% / 32.6% | 0.090% / 0.120% | 83% | 1 | contradicts: Sharpe 1.48 < buy&hold 1.51 | [QQQ_2023-01-03_2026-10-09_20261012T032100Z.json](../backtests/vol_target_v1/QQQ_2023-01-03_2026-10-09_20261012T032100Z.json) |

---

## Idea B: Multi-horizon time-series momentum ladder

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 3
- **Strategy file:** `strategies/tsmom_ladder_v1.py`

### Hypothesis
Holding SPY/QQQ at weight equal to the fraction of the 21-, 63-, 126- and 252-trading-day trailing close-to-close returns that are positive (so 0, 0.25, 0.5, 0.75 or 1) beats buy-and-hold on Sharpe and cuts max drawdown by at least 5 points after 5 bps costs. This must hold in both 2016-2022 and 2023-onward.

### Why it might work
- Time-series momentum is documented across asset classes (Moskowitz, Ooi and Pedersen, 2012). It comes from slow information diffusion, herding, and investors who under-react and then over-react.
- The 21- and 63-day legs cut exposure to 0.5 or less within weeks of a fast crash. The 50/200 SMA could not do that in 2020.
- The 126- and 252-day legs keep one month of noise from flattening the whole position.
- Graded weights mean partial de-risking, not all-or-nothing whipsaws.
- Who is on the other side: rebalancers and mean-reversion traders who sell strength and buy weakness.

### Market conditions it needs
- Drawdowns that last more than about a month: 2018 Q4, 2020 and 2022.
- Recoveries that persist long enough for the short legs to turn positive again.

### How it could fail
- Kill threshold: Sharpe below buy-and-hold on either window, or max drawdown not at least 5 points better than buy-and-hold on either window, for either symbol (5 bps costs).
- Likely ways to fail:
  - Choppy, range-bound markets that whipsaw the 21-day leg.
  - V-shaped recoveries that leave it underweight at the bottom, for example in 2020 and 2025.

### Test plan
- Symbols: SPY and QQQ, each tested separately.
- Windows: 2016-01-01..2022-12-31 and 2023-01-01..2026-10-09.
- Costs: 5 bps.
- Benchmark: buy-and-hold on the same symbol.
- Report: Sharpe, max drawdown, CAGR, average exposure and turnover.
- Fixed lookbacks: 21, 63, 126 and 252 days. No parameter sweep.

### Results

**Verdict: rejected** (round 1, 2026-10-12; rule fixed before testing, scored by `research/round1_verdicts.py`). Strategy: `strategies/tsmom_ladder_v1.py`.

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Ret per exposure day (strat / B&H mean) | Exposure | Entries | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|
| SPY IS | 0.64 / 0.68 | -16.7% / -33.8% | 6.2% / 11.5% | 0.028% / 0.050% | 71% | 12 | contradicts: Sharpe 0.64 < buy&hold 0.68 | [SPY_2016-01-04_2022-12-30_20261012T032100Z.json](../backtests/tsmom_ladder_v1/SPY_2016-01-04_2022-12-30_20261012T032100Z.json) |
| SPY OOS | 1.44 / 1.43 | -9.4% / -18.8% | 15.5% / 22.4% | 0.060% / 0.085% | 84% | 5 | supports: passes kill threshold | [SPY_2023-01-03_2026-10-09_20261012T032100Z.json](../backtests/tsmom_ladder_v1/SPY_2023-01-03_2026-10-09_20261012T032100Z.json) |
| QQQ IS | 0.72 / 0.70 | -24.5% / -35.0% | 9.6% / 14.5% | 0.044% / 0.065% | 71% | 19 | supports: passes kill threshold | [QQQ_2016-01-04_2022-12-30_20261012T032100Z.json](../backtests/tsmom_ladder_v1/QQQ_2016-01-04_2022-12-30_20261012T032100Z.json) |
| QQQ OOS | 1.40 / 1.51 | -14.5% / -22.8% | 21.8% / 32.6% | 0.083% / 0.120% | 83% | 2 | contradicts: Sharpe 1.40 < buy&hold 1.51 | [QQQ_2023-01-03_2026-10-09_20261012T032100Z.json](../backtests/tsmom_ladder_v1/QQQ_2023-01-03_2026-10-09_20261012T032100Z.json) |

---

## Idea C: Donchian breakout with 21-day-low exit

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 4
- **Strategy file:** `strategies/donchian_breakout_v1.py`

### Hypothesis
- Rule: go long SPY/QQQ (weight 1) after a close at a new 63-day closing high.
- Go flat (weight 0) after a close below the lowest close of the prior 21 days.
- Stay flat until the next 63-day closing high.

This rule beats buy-and-hold on Sharpe and cuts max drawdown by at least 5 points after 5 bps costs, in both 2016-2022 and 2023-onward.

### Why it might work
- A close under the prior 21-day low is a price-only exit. It fires a few days into a fast crash, around the last week of February 2020, instead of months later as the 50/200 cross did.
- Requiring a fresh 63-day high before re-entering keeps it out of bear-market rallies, such as those in 2022.
- Who is on the other side: dip buyers and value or rebalance flows that average into falling markets.
- Systematic trend followers (CTAs) using similar channels add to the move after the breakout.

### Market conditions it needs
- Sharp sell-offs that break the 21-day low early: 2018 Q4, 2020, 2022 and April 2025.
- Trending recoveries that make new 63-day highs reasonably soon after the bottom.

### How it could fail
- Kill threshold: Sharpe below buy-and-hold on either window, or max drawdown not at least 5 points better than buy-and-hold on either window, for either symbol (5 bps costs).
- Likely ways to fail:
  - Frequent shallow pullbacks that trigger the exit, followed by re-entry at a higher price.
  - Waiting for a 63-day high after a V-bottom, which misses much of the rebound.

### Test plan
- Symbols: SPY and QQQ, each tested separately.
- Windows: 2016-01-01..2022-12-31 and 2023-01-01..2026-10-09.
- Costs: 5 bps.
- Benchmark: buy-and-hold on the same symbol.
- Report: Sharpe, max drawdown, CAGR, time in market and number of round trips.
- Fixed channels: 63-day entry and 21-day exit. No parameter sweep.
- Starting state: flat until the first 63-day high.

### Results

**Verdict: rejected** (round 1, 2026-10-12; rule fixed before testing, scored by `research/round1_verdicts.py`). Strategy: `strategies/donchian_breakout_v1.py`.

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Ret per exposure day (strat / B&H mean) | Exposure | Entries | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|
| SPY IS | 0.50 / 0.68 | -12.5% / -33.8% | 3.9% / 11.5% | 0.032% / 0.050% | 52% | 19 | contradicts: Sharpe 0.50 < buy&hold 0.68 | [SPY_2016-01-04_2022-12-30_20261012T032100Z.json](../backtests/donchian_breakout_v1/SPY_2016-01-04_2022-12-30_20261012T032100Z.json) |
| SPY OOS | 1.01 / 1.43 | -7.9% / -18.8% | 8.6% / 22.4% | 0.058% / 0.085% | 59% | 12 | contradicts: Sharpe 1.01 < buy&hold 1.43 | [SPY_2023-01-03_2026-10-09_20261012T032100Z.json](../backtests/donchian_breakout_v1/SPY_2023-01-03_2026-10-09_20261012T032100Z.json) |
| QQQ IS | 0.58 / 0.70 | -16.6% / -35.0% | 5.8% / 14.5% | 0.048% / 0.065% | 51% | 17 | contradicts: Sharpe 0.58 < buy&hold 0.70 | [QQQ_2016-01-04_2022-12-30_20261012T032100Z.json](../backtests/donchian_breakout_v1/QQQ_2016-01-04_2022-12-30_20261012T032100Z.json) |
| QQQ OOS | 1.21 / 1.51 | -10.5% / -22.8% | 14.9% / 32.6% | 0.109% / 0.120% | 53% | 9 | contradicts: Sharpe 1.21 < buy&hold 1.51 | [QQQ_2023-01-03_2026-10-09_20261012T032100Z.json](../backtests/donchian_breakout_v1/QQQ_2023-01-03_2026-10-09_20261012T032100Z.json) |
