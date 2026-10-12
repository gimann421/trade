# Round 2 volatility-regime ideas (IWM, TLT, GLD, XLE, EFA)

- **Date:** 2026-10-12
- **Analyst:** volatility-regime-analyst (round 2)
- **Ledger hypothesis ids:** 20, 21, 22
- **Strategy file:** `strategies/good_bad_vol_filter_v1.py` (H20), `strategies/squeeze_release_v1.py` (H21), `strategies/vol_peak_rebound_v1.py` (H22)

No returns were computed and no backtest was run; every parameter below is fixed from convention or reasoning, not from these data. Only row counts were checked (2,710 daily rows per symbol).

## Common scoring rules (all three ideas)
- Cells: 5 symbols x {IS 2016-01-01..2022-12-31, OOS 2023-01-01..end}; 5 bps; signals on full history, then sliced.
- SUPPORTED only if both windows support on >= 4 of 5 symbols (`symbol_status(min_symbols=4)`) AND mean placebo percentile over passing cells >= 0.95 (`placebo_percentile`, 1000 circular shifts, metric stated per idea).
- A cell below its minimum event count is inconclusive (counts as not passing, so with 4/5 required, at most one symbol may be inconclusive or failing).
- Buy-and-hold-is-weak guard: every threshold is additive (not a multiple of B&H) and each idea has an absolute floor; a "reject outright" rule applies if any single cell fails badly.
- Rejected earlier ideas not repeated: H2 (vol targeting), H8 (10d/100d ratio switch), H9 (gap cluster), H10 (range-shock timeout). Not duplicated: H14-H19.

## Idea 1 (H20): Good-vol/bad-vol filter, exit when vol is above normal and >= 70% downside

### Hypothesis
Holding each symbol at weight 1, but at weight 0 while 20d vol of daily log returns exceeds its trailing-252d median AND the 20d downside semivariance share DS20 = sum(r^2 where r<0) / sum(r^2) is >= 0.70 (re-enter when vol20 <= that median OR DS20 <= 0.50; weight 1 during the 272-day warmup), beats buy-and-hold per cell on Sharpe and drawdown.

### Why it might work
Vol is only a risk signal when it comes from falling prices. Equities/XLE show the leverage effect (vol up with price down); long bonds in a rate sell-off have vol up with price down and no safe-haven bid; gold and bonds in rallies have vol up with price up ("good vol", no reason to exit). Conditioning on the sign of the squared returns separates these in a single rule. Why it differs from H2/H8/H10: those react to vol level, ratio or a range shock, direction-blind, so they exit on good vol and on one-day spikes and gave up the rebound; this one needs a sustained (20d) downside-dominated regime, which is when returns are persistently negative (sell-off momentum, deleveraging and forced selling spread over weeks). H14-H16 are price-level/drawdown rules; this is a return-distribution-shape rule. Other side: holders who stay long through downside-dominated vol clusters (benchmarked allocators, dip buyers early in a sell-off); risk-parity/vol-target funds sell later.
Parameters: 20d and 252d (one month and one year, standard windows); 0.70 and 0.50 (symmetric noise gives ~0.5; 0.70 = clearly one-sided, 0.50 re-entry = hysteresis back to neutral), reasoned not fitted.

### How it could fail
Per cell (precise, codable): PASS iff B&H Sharpe >= 0.20 AND Sharpe >= B&H Sharpe + 0.05 AND MaxDD at least 5 points shallower than B&H (i.e. `drawdown_rule(0.05, 1.0)` plus the additive 0.05 Sharpe margin). Inconclusive if B&H Sharpe < 0.20 (nothing to protect) or fewer than 6 exits in IS / 3 in OOS. Reject outright if any cell has Sharpe < B&H Sharpe - 0.15, or the hypothesis misses the 4-of-5 rule. Placebo metric: `sharpe`, percentile >= 0.95. Also wrong if the filter fires mainly on gold/bond rallies (check exit days' mean return sign is negative: informational).

### Test plan
IWM, TLT, GLD, XLE, EFA, windows above, 5 bps, benchmark B&H same symbol. Daily position so turnover is only at exits/entries (binary weights).

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/good_bad_vol_filter_v1.py`.

Notes: veto: GLD IS: Sharpe 0.30 more than 0.15 below buy&hold 0.57; GLD OOS: Sharpe 0.87 more than 0.15 below buy&hold 1.18; XLE OOS: Sharpe 0.36 more than 0.15 below buy&hold 0.74; EFA OOS: Sharpe 0.80 more than 0.15 below buy&hold 1.08

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.48 / 0.45 | -38.4% / -41.3% | 7.5% / 8.2% | 0.042% / 0.042% | 0.54 | 84% | 20 / 19 / 19 | contradicts: MaxDD -38.4% not 5pts better than -41.3%; Sharpe 0.48 < buy&hold 0.45 + 0.05 | [IWM_2016-01-04_2022-12-30_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/IWM_2016-01-04_2022-12-30_20261012T150157Z.json) |
| IWM OOS | 0.72 / 0.76 | -20.4% / -27.5% | 12.5% / 14.6% | 0.059% / 0.062% | 0.76 | 91% | 10 / 9 / 9 | contradicts: Sharpe 0.72 < 1x buy&hold 0.76; Sharpe 0.72 < buy&hold 0.76 + 0.05 | [IWM_2023-01-03_2026-10-12_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/IWM_2023-01-03_2026-10-12_20261012T150157Z.json) |
| TLT IS | 0.08 / 0.03 | -36.9% / -44.1% | 0.2% / -0.7% | 0.005% / 0.002% | 0.10 | 86% | 18 / 17 / 17 | inconclusive: buy&hold Sharpe 0.03 < 0.20 (nothing to protect) | [TLT_2016-01-04_2022-12-30_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/TLT_2016-01-04_2022-12-30_20261012T150157Z.json) |
| TLT OOS | -0.21 / -0.10 | -20.6% / -22.4% | -3.5% / -2.4% | -0.012% / -0.006% | -0.21 | 89% | 6 / 6 / 6 | inconclusive: buy&hold Sharpe -0.10 < 0.20 (nothing to protect) | [TLT_2023-01-03_2026-10-12_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/TLT_2023-01-03_2026-10-12_20261012T150157Z.json) |
| GLD IS | 0.30 / 0.57 | -28.5% / -22.0% | 3.2% / 7.4% | 0.018% / 0.032% | 0.34 | 86% | 24 / 23 / 23 | contradicts: Sharpe 0.30 < 1x buy&hold 0.57; MaxDD -28.5% not 5pts better than -22.0%; Sharpe 0.30 < buy&hold 0.57 + 0.05 | [GLD_2016-01-04_2022-12-30_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/GLD_2016-01-04_2022-12-30_20261012T150157Z.json) |
| GLD OOS | 0.87 / 1.18 | -38.9% / -26.4% | 15.2% / 24.1% | 0.072% / 0.094% | 0.94 | 87% | 11 / 10 / 10 | contradicts: Sharpe 0.87 < 1x buy&hold 1.18; MaxDD -38.9% not 5pts better than -26.4%; Sharpe 0.87 < buy&hold 1.18 + 0.05 | [GLD_2023-01-03_2026-10-12_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/GLD_2023-01-03_2026-10-12_20261012T150157Z.json) |
| XLE IS | 0.73 / 0.46 | -38.8% / -66.8% | 17.0% / 10.0% | 0.088% / 0.059% | 0.79 | 86% | 14 / 13 / 13 | supports: passes kill threshold | [XLE_2016-01-04_2022-12-30_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/XLE_2016-01-04_2022-12-30_20261012T150157Z.json) |
| XLE OOS | 0.36 / 0.74 | -32.6% / -20.1% | 5.3% / 15.1% | 0.032% / 0.066% | 0.40 | 86% | 13 / 12 / 12 | contradicts: Sharpe 0.36 < 1x buy&hold 0.74; MaxDD -32.6% not 5pts better than -20.1%; Sharpe 0.36 < buy&hold 0.74 + 0.05 | [XLE_2023-01-03_2026-10-12_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/XLE_2023-01-03_2026-10-12_20261012T150157Z.json) |
| EFA IS | 0.26 / 0.35 | -38.3% / -34.2% | 2.6% / 4.8% | 0.017% / 0.026% | 0.30 | 81% | 19 / 18 / 18 | contradicts: Sharpe 0.26 < 1x buy&hold 0.35; MaxDD -38.3% not 5pts better than -34.2%; Sharpe 0.26 < buy&hold 0.35 + 0.05 | [EFA_2016-01-04_2022-12-30_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/EFA_2016-01-04_2022-12-30_20261012T150157Z.json) |
| EFA OOS | 0.80 / 1.08 | -19.3% / -14.1% | 10.3% / 16.2% | 0.047% / 0.064% | 0.85 | 91% | 9 / 8 / 8 | contradicts: Sharpe 0.80 < 1x buy&hold 1.08; MaxDD -19.3% not 5pts better than -14.1%; Sharpe 0.80 < buy&hold 1.08 + 0.05 | [EFA_2023-01-03_2026-10-12_20261012T150157Z.json](../backtests/good_bad_vol_filter_v1/EFA_2023-01-03_2026-10-12_20261012T150157Z.json) |

## Idea 2 (H21): Squeeze-release long, upside breakout after range compression

### Hypothesis
Going long (weight 1) at a close that is above the highest close of the prior 10 days while ATR%10 (10d mean true range / close) was <= its 20th percentile of the trailing 250 days on at least one of the last 5 closes, exiting at the first close below the lowest close of the prior 10 days or after 40 trading days (flat otherwise; flat for the first 260 days), earns a higher return per exposure day and conditional Sharpe than buy-and-hold.

### Why it might work
Volatility clusters and mean-reverts, so a compressed range precedes an expansion; direction is unknown, but a long-only rule that waits for the upside close selects the good-vol expansions (rallies in gold/bonds/equities) and ignores down-expansions, using the asymmetry directly. It is not Donchian H4 (price-only breakout, no compression requirement, 63d) and not a de-risk rule like H8/H10. The compression condition makes entries rare and event-driven, exposure low. Other side: range traders and short-vol/short-gamma sellers fading moves out of quiet ranges who must cover, plus late trend-followers. Parameters: ATR 10d, 250d percentile window (1 year), 20th percentile (Bollinger squeeze convention), 10-day breakout/exit (Crabel/Donchian short-channel convention), 40d cap (two months).

### How it could fail
Per cell PASS iff return per exposure day >= 3 bps AND >= B&H mean daily return + 3 bps, AND conditional exposure-day annualised Sharpe (mean/std of strategy daily returns on days with position>0, x sqrt(252)) >= B&H full-window Sharpe + 0.10. Inconclusive if fewer than 10 entries in IS or 4 in OOS. Reject outright if any cell has return per exposure day < 0. Placebo metric: `return_per_exposure_day`, percentile >= 0.95. Wrong if exposure in a cell is <3% of days (too sparse to matter).

### Test plan
Same symbols/windows/costs. Benchmark B&H same symbol. Round trips pay 10 bps; with ~40-day max holds this is small versus the target edge.

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/squeeze_release_v1.py`.

Notes: veto: IWM IS: return/exposure day -0.026% below 0; TLT OOS: return/exposure day -0.110% below 0; EFA IS: return/exposure day -0.002% below 0; EFA OOS: return/exposure day -0.001% below 0

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | -0.21 / 0.45 | -19.1% / -41.3% | -1.3% / 8.2% | -0.026% / 0.042% | -0.44 | 18% | 22 / 22 / 22 | contradicts: return/exposure day -0.026% < 3bps; return/exposure day -0.026% < buy&hold mean 0.042% + 3bps; conditional Sharpe -0.44 < buy&hold 0.45 + 0.10 | [IWM_2016-01-04_2022-12-30_20261012T150157Z.json](../backtests/squeeze_release_v1/IWM_2016-01-04_2022-12-30_20261012T150157Z.json) |
| IWM OOS | 0.39 / 0.76 | -12.8% / -27.5% | 3.7% / 14.6% | 0.050% / 0.062% | 0.71 | 34% | 19 / 19 / 19 | contradicts: return/exposure day 0.050% < buy&hold mean 0.062% + 3bps; conditional Sharpe 0.71 < buy&hold 0.76 + 0.10 | [IWM_2023-01-03_2026-10-12_20261012T150158Z.json](../backtests/squeeze_release_v1/IWM_2023-01-03_2026-10-12_20261012T150158Z.json) |
| TLT IS | 0.32 / 0.03 | -6.9% / -44.1% | 1.5% / -0.7% | 0.031% / 0.002% | 0.77 | 20% | 20 / 20 / 20 | contradicts: return/exposure day 0.031% < buy&hold mean 0.002% + 3bps | [TLT_2016-01-04_2022-12-30_20261012T150158Z.json](../backtests/squeeze_release_v1/TLT_2016-01-04_2022-12-30_20261012T150158Z.json) |
| TLT OOS | -1.07 / -0.10 | -27.4% / -22.4% | -7.8% / -2.4% | -0.110% / -0.006% | -1.92 | 28% | 26 / 26 / 26 | contradicts: return/exposure day -0.110% < 3bps; return/exposure day -0.110% < buy&hold mean -0.006% + 3bps; conditional Sharpe -1.92 < buy&hold -0.10 + 0.10 | [TLT_2023-01-03_2026-10-12_20261012T150158Z.json](../backtests/squeeze_release_v1/TLT_2023-01-03_2026-10-12_20261012T150158Z.json) |
| GLD IS | 0.22 / 0.57 | -17.1% / -22.0% | 1.3% / 7.4% | 0.022% / 0.032% | 0.47 | 27% | 29 / 28 / 28 | contradicts: return/exposure day 0.022% < 3bps; return/exposure day 0.022% < buy&hold mean 0.032% + 3bps; conditional Sharpe 0.47 < buy&hold 0.57 + 0.10 | [GLD_2016-01-04_2022-12-30_20261012T150158Z.json](../backtests/squeeze_release_v1/GLD_2016-01-04_2022-12-30_20261012T150158Z.json) |
| GLD OOS | 1.46 / 1.18 | -8.4% / -26.4% | 13.2% / 24.1% | 0.198% / 0.094% | 2.96 | 26% | 11 / 11 / 11 | supports: passes kill threshold | [GLD_2023-01-03_2026-10-12_20261012T150158Z.json](../backtests/squeeze_release_v1/GLD_2023-01-03_2026-10-12_20261012T150158Z.json) |
| XLE IS | 0.51 / 0.46 | -19.3% / -66.8% | 4.7% / 10.0% | 0.108% / 0.059% | 1.22 | 19% | 20 / 19 / 19 | supports: passes kill threshold | [XLE_2016-01-04_2022-12-30_20261012T150158Z.json](../backtests/squeeze_release_v1/XLE_2016-01-04_2022-12-30_20261012T150158Z.json) |
| XLE OOS | 0.06 / 0.74 | -28.1% / -20.1% | 0.0% / 15.1% | 0.008% / 0.066% | 0.15 | 36% | 25 / 24 / 24 | contradicts: return/exposure day 0.008% < 3bps; return/exposure day 0.008% < buy&hold mean 0.066% + 3bps; conditional Sharpe 0.15 < buy&hold 0.74 + 0.10 | [XLE_2023-01-03_2026-10-12_20261012T150158Z.json](../backtests/squeeze_release_v1/XLE_2023-01-03_2026-10-12_20261012T150158Z.json) |
| EFA IS | -0.03 / 0.35 | -15.1% / -34.2% | -0.3% / 4.8% | -0.002% / 0.026% | 0.02 | 26% | 26 / 26 / 26 | contradicts: return/exposure day -0.002% < 3bps; return/exposure day -0.002% < buy&hold mean 0.026% + 3bps; conditional Sharpe 0.02 < buy&hold 0.35 + 0.10 | [EFA_2016-01-04_2022-12-30_20261012T150158Z.json](../backtests/squeeze_release_v1/EFA_2016-01-04_2022-12-30_20261012T150158Z.json) |
| EFA OOS | -0.01 / 1.08 | -17.1% / -14.1% | -0.3% / 16.2% | -0.001% / 0.064% | 0.05 | 32% | 20 / 20 / 20 | contradicts: return/exposure day -0.001% < 3bps; return/exposure day -0.001% < buy&hold mean 0.064% + 3bps; conditional Sharpe 0.05 < buy&hold 1.08 + 0.10 | [EFA_2023-01-03_2026-10-12_20261012T150158Z.json](../backtests/squeeze_release_v1/EFA_2023-01-03_2026-10-12_20261012T150158Z.json) |

## Idea 3 (H22): Post-spike vol-peak rebound long, 20-day hold

### Hypothesis
Going long (weight 1) at the close when 20d realized vol was >= its trailing-500d 90th percentile on at least one of the last 10 closes AND today's vol20 <= 0.90 x the maximum vol20 of the last 10 closes (the spike has peaked), holding exactly 20 trading days (triggers during a hold ignored; flat otherwise and for the first 520 days), earns higher return per exposure day than buy-and-hold.

### Why it might work
After vol spikes, risk premia (equity, bond term, gold) and the variance risk premium are richest because forced sellers (margin calls, risk-parity and vol-target deleveraging, stop-outs) exit at the peak of vol irrespective of value; vol then mean-reverts and prices rebound. Waiting until vol has rolled off its maximum avoids the knife-catch that H10 de-risked into, and it is the opposite timing of H2/H8/H10, which hold the spike out and forfeit the rebound (their round-1 return give-up). It differs from H19 (volume-conditioned 3-day return reversal, 5d hold) and H17/H18 (price z-score) by being triggered by realized-vol regime, not price or volume, and by a 20-day hold. Asymmetry test: in equities the spike is a price decline (reversal), in bonds/gold it may follow rallies or sell-offs; one rule is applied identically. Other side: forced deleveragers. Parameters: 20d vol, 500d window (~2 years), 90th percentile, 10-day lookback, 0.90 peak factor, 20-day hold: conventional round numbers, not fitted.

### How it could fail
Per cell PASS iff return per exposure day >= B&H mean daily return + 5 bps AND conditional exposure-day annualised Sharpe >= B&H full-window Sharpe. Inconclusive if fewer than 4 entries in a window. Reject outright if any cell has return per exposure day < 0. Placebo metric: `return_per_exposure_day`, percentile >= 0.95. Note: few spikes occur in OOS, so inconclusive cells are likely; that is accepted rather than loosened.

### Test plan
Same symbols/windows/costs/benchmark. Because the long window is flat most of the time, only per-exposure and conditional metrics are used (full-window Sharpe would be dominated by low exposure).

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/vol_peak_rebound_v1.py`.

Notes: veto: IWM OOS: return/exposure day -0.038% below 0; TLT IS: return/exposure day -0.006% below 0; GLD IS: return/exposure day -0.003% below 0; GLD OOS: return/exposure day -0.050% below 0; XLE OOS: return/exposure day -0.097% below 0

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.34 / 0.45 | -15.8% / -41.3% | 3.0% / 8.2% | 0.100% / 0.042% | 0.96 | 14% | 12 / 12 / 12 | supports: passes kill threshold | [IWM_2016-01-04_2022-12-30_20261012T150158Z.json](../backtests/vol_peak_rebound_v1/IWM_2016-01-04_2022-12-30_20261012T150158Z.json) |
| IWM OOS | -0.12 / 0.76 | -12.3% / -27.5% | -0.8% / 14.6% | -0.038% / 0.062% | -0.42 | 6% | 3 / 3 / 3 | inconclusive: only 3 entries (need 4) | [IWM_2023-01-03_2026-10-12_20261012T150158Z.json](../backtests/vol_peak_rebound_v1/IWM_2023-01-03_2026-10-12_20261012T150158Z.json) |
| TLT IS | -0.03 / 0.03 | -25.1% / -44.1% | -0.5% / -0.7% | -0.006% / 0.002% | -0.04 | 18% | 16 / 16 / 16 | contradicts: return/exposure day -0.006% < buy&hold mean 0.002% + 5bps; conditional Sharpe -0.04 < buy&hold 0.03 | [TLT_2016-01-04_2022-12-30_20261012T150158Z.json](../backtests/vol_peak_rebound_v1/TLT_2016-01-04_2022-12-30_20261012T150158Z.json) |
| TLT OOS | 0.86 / -0.10 | -5.4% / -22.4% | 3.8% / -2.4% | 0.238% / -0.006% | 3.51 | 6% | 3 / 3 / 3 | inconclusive: only 3 entries (need 4) | [TLT_2023-01-03_2026-10-12_20261012T150158Z.json](../backtests/vol_peak_rebound_v1/TLT_2023-01-03_2026-10-12_20261012T150158Z.json) |
| GLD IS | -0.02 / 0.57 | -9.9% / -22.0% | -0.2% / 7.4% | -0.003% / 0.032% | -0.01 | 10% | 9 / 8 / 8 | contradicts: return/exposure day -0.003% < buy&hold mean 0.032% + 5bps; conditional Sharpe -0.01 < buy&hold 0.57 | [GLD_2016-01-04_2022-12-30_20261012T150158Z.json](../backtests/vol_peak_rebound_v1/GLD_2016-01-04_2022-12-30_20261012T150158Z.json) |
| GLD OOS | -0.23 / 1.18 | -24.4% / -26.4% | -3.4% / 24.1% | -0.050% / 0.094% | -0.47 | 22% | 11 / 11 / 11 | contradicts: return/exposure day -0.050% < buy&hold mean 0.094% + 5bps; conditional Sharpe -0.47 < buy&hold 1.18 | [GLD_2023-01-03_2026-10-12_20261012T150159Z.json](../backtests/vol_peak_rebound_v1/GLD_2023-01-03_2026-10-12_20261012T150159Z.json) |
| XLE IS | 0.37 / 0.46 | -23.7% / -66.8% | 4.2% / 10.0% | 0.148% / 0.059% | 1.03 | 14% | 12 / 12 / 12 | supports: passes kill threshold | [XLE_2016-01-04_2022-12-30_20261012T150159Z.json](../backtests/vol_peak_rebound_v1/XLE_2016-01-04_2022-12-30_20261012T150159Z.json) |
| XLE OOS | -0.24 / 0.74 | -18.8% / -20.1% | -3.2% / 15.1% | -0.097% / 0.066% | -0.70 | 11% | 5 / 5 / 5 | contradicts: return/exposure day -0.097% < buy&hold mean 0.066% + 5bps; conditional Sharpe -0.70 < buy&hold 0.74 | [XLE_2023-01-03_2026-10-12_20261012T150159Z.json](../backtests/vol_peak_rebound_v1/XLE_2023-01-03_2026-10-12_20261012T150159Z.json) |
| EFA IS | 0.25 / 0.35 | -19.1% / -34.2% | 1.5% / 4.8% | 0.057% / 0.026% | 0.74 | 12% | 11 / 10 / 10 | contradicts: return/exposure day 0.057% < buy&hold mean 0.026% + 5bps | [EFA_2016-01-04_2022-12-30_20261012T150159Z.json](../backtests/vol_peak_rebound_v1/EFA_2016-01-04_2022-12-30_20261012T150159Z.json) |
| EFA OOS | 0.36 / 1.08 | -11.2% / -14.1% | 2.6% / 16.2% | 0.132% / 0.064% | 1.25 | 9% | 5 / 5 / 5 | supports: passes kill threshold | [EFA_2023-01-03_2026-10-12_20261012T150159Z.json](../backtests/vol_peak_rebound_v1/EFA_2023-01-03_2026-10-12_20261012T150159Z.json) |
