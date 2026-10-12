# Round 2 mean reversion: three ideas on IWM, TLT, GLD, XLE, EFA

- **Date:** 2026-10-12
- **Analyst:** mean-reversion-analyst (round 2)
- **Ledger hypothesis ids:** 17 (A), 18 (B), 19 (C)
- **Strategy file:** `strategies/bollinger_stepaside_v1.py` (H17), `strategies/mean_reversion_z50_v1.py` (H18), `strategies/volume_shock_reversal_v1.py` (H19)

No returns, backtests or tuning were run. Only row counts were checked (2,709 daily rows per symbol, 2016-01-04 to 2026-10-12). Every parameter below is fixed from published convention or reasoning, stated per idea. None of the ideas touch SPY or QQQ. None repeat H1-H13 (H5 RSI(2), H6 three down closes, H7 IBS are the only mean-reversion ones; see "Difference from round 1").

## Shared design (applies to all three ideas)

**Long-only.** Weights are in [0, 1]. Overbought reversal can only be expressed as stepping aside (idea A). No shorts.

**Scoring cells.** 5 symbols x 2 windows (IS 2016-01-01..2022-12-31, OOS 2023-01-01..end), 5 bps per unit turnover, signals on full history.

**Pass rule (fixed).** SUPPORTED only if `symbol_status(cells, min_symbols=4)` is "supported" (at least 4 of 5 symbols pass both windows) AND the mean placebo percentile over the passing cells is >= 0.95. Placebo = `placebo_percentile` with the metric named per idea, 1000 shifts, seed 0, min_shift 252. A cell with fewer entries than the minimum is "inconclusive" (not a pass, not a contradiction). REJECTED when `symbol_status` says so, or when a stated veto fires.

**Why the kill rules are additive, not multiplicative.** TLT, GLD and XLE buy-and-hold means and Sharpes can be near zero or negative in a window (TLT 2022 and 2023 onward is the obvious case), so "2x buy-and-hold" is meaningless there. All thresholds are of the form "B&H value plus a fixed amount". With a negative B&H mean, +5 bps/day still demands a positive absolute edge. These are custom rules (not `per_day_rule`) and need a small helper in the round script. Definitions, to be coded literally:
- `rped` = strategy `return_per_exposure_day` (sum of net daily returns / days with position > 0).
- `bh_mean` = buy-and-hold `mean_daily_return`; `bh_sharpe` = buy-and-hold Sharpe.
- `cond_sharpe` = mean(net daily returns on days with position > 0) / std(same, ddof=1) x sqrt(252). This is the risk-adjusted condition that is fair to part-time strategies: the total Sharpe of a strategy that is flat 90% of the time is mechanically diluted and was exactly what killed H5-H7.

**Costs and fill optimism (all ideas).** The backtester fills at the signal day's close. Signals are computed from that same close, so the trade assumes a market-on-close order sized from a price that is not known until the close. For ideas B and C the entry day is a stressed-selling day where the close is typically a wide-spread print, so entry optimism is real: I expect realistic slippage of a few bps beyond the 5 bps modelled. Idea A trades rarely and exits a spike at the close, so it carries the least cost sensitivity. No separate optimism haircut is applied; the tests use 5 bps as specified and the memo flags that any cell passing by less than the margin below should be treated with suspicion.

## Difference from round 1 (H5, H6, H7)

Round 1 used a below-200d-SMA-excluded entry on SPY/QQQ, exposure 5-16%, hold 1-5 days, and per-day edge that was real but diluted. The ideas here change:
- **A: time structure.** In the market ~90% of days by default; the signal removes days. The H5-H7 exposure failure mode does not apply.
- **B: trigger and exit.** Multi-week distance from the 50d mean, exit at the mean or 30 days; no 200d filter (no drift to filter on).
- **C: trigger mechanism.** Volume-confirmed liquidity shock, scaled by own volatility; not a down-close count, RSI(2) or close location.

Market conditions: SPY/QQQ drifted up strongly from 2023, which made a flat-most-of-the-time strategy lose to buy-and-hold. GLD, TLT, XLE, IWM, EFA do not share that drift (TLT fell in 2022 and was weak after; GLD and XLE are regime-driven), so the per-day edge should matter more, but that is an assumption to be tested, not a finding.

---

## Idea A (hypothesis 17): Bollinger overbought step-aside

- **Ledger hypothesis id:** 17
- **Strategy file:** `strategies/bollinger_stepaside_v1.py`

### Hypothesis
Holding each of IWM/TLT/GLD/XLE/EFA at weight 1 by default, but stepping to 0 from the close where z = (close - SMA20) / std20 exceeds 2.0 until the first close with z < 0 (weight 1 in warmup), improves Sharpe by at least 0.10 and does not worsen max drawdown versus buy-and-hold, after 5 bps, daily bars.

### Fixed parameters and sources
SMA window 20 and 2.0 standard deviations: Bollinger band defaults (Bollinger, 1992). std is the population std of the same 20 closes (as in the Bollinger definition). Re-entry at the mean (z < 0): the band midpoint, the standard "reversion complete" level. Hysteresis (exit >2, re-enter <0) avoids flip-flopping; it is not tuned. Overbought is expressed as a long-only exit, since shorting is forbidden.

### Why it might work
Short-horizon reversal after extreme moves (Jegadeesh 1990; Lehmann 1990) is strongest in assets whose spikes are flow or headline driven: gold on risk-off bursts, long bonds on auction/flight-to-quality days, energy on supply headlines. Who is on the other side: momentum chasers and flow-driven buyers paying up at the top of the band, who are then the supply as price retraces. By being out for 2-sigma extensions we sell to them and buy back near the mean. Because we are in the market ~90% of days, the Sharpe comparison with buy-and-hold is fair.

### Exact market conditions needed
- Assets must oscillate around a 20-day mean rather than trend persistently for months. In a steady uptrend z stays above 2 only briefly, so this costs a little; in a one-way melt-up (z above 2 for weeks) it costs a lot.
- Needs enough 2-sigma events: with roughly normal daily noise, z > 2 on the order of a few percent of days, i.e. at least 15 step-asides in IS and 8 in OOS for a cell to count.
- Costs: a round trip is two trades, 10 bps; the avoided loss per step-aside must exceed about 10 bps. Fill optimism: exit at the close of the spike day is a close-based decision, which is feasible with an MOC order, so optimism is small.

### How it could fail (decide now)
A cell fails if ANY of: Sharpe < B&H Sharpe + 0.10; max drawdown more than 0 pts worse than B&H (i.e. strategy MaxDD < B&H MaxDD); rped < bh_mean + 1 bp (1 bp/day is about 2.5%/yr at 90% exposure). Inconclusive if fewer than 15 (IS) or 8 (OOS) step-asides. Veto: any cell with MaxDD more than 5 pts worse than B&H rejects the hypothesis regardless of the 4/5 count. Placebo metric: **sharpe** (the position is in the market most days, so the Sharpe is the relevant statistic and placebo shifts keep exposure and trade count).

### Test plan
Run on all 5 symbols, both windows, 5 bps, benchmark buy-and-hold same symbol. Pass rule as in the shared section.

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/bollinger_stepaside_v1.py`.

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.33 / 0.45 | -40.9% / -41.3% | 4.8% / 8.2% | 0.041% / 0.042% | 0.41 | 68% | 34 / 33 / 33 | contradicts: Sharpe 0.33 < buy&hold 0.45 + 0.10; return/exposure day 0.041% < buy&hold mean 0.042% + 1bp | [IWM_2016-01-04_2022-12-30_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/IWM_2016-01-04_2022-12-30_20261012T150155Z.json) |
| IWM OOS | 0.80 / 0.76 | -24.2% / -27.5% | 13.2% / 14.6% | 0.086% / 0.062% | 1.02 | 64% | 21 / 20 / 20 | contradicts: Sharpe 0.80 < buy&hold 0.76 + 0.10 | [IWM_2023-01-03_2026-10-12_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/IWM_2023-01-03_2026-10-12_20261012T150155Z.json) |
| TLT IS | -0.18 / 0.03 | -42.0% / -44.1% | -3.0% / -0.7% | -0.013% / 0.002% | -0.19 | 72% | 28 / 27 / 27 | contradicts: Sharpe -0.18 < buy&hold 0.03 + 0.10; return/exposure day -0.013% < buy&hold mean 0.002% + 1bp | [TLT_2016-01-04_2022-12-30_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/TLT_2016-01-04_2022-12-30_20261012T150155Z.json) |
| TLT OOS | 0.27 / -0.10 | -22.5% / -22.4% | 2.6% / -2.4% | 0.018% / -0.006% | 0.34 | 74% | 24 / 23 / 23 | contradicts: MaxDD -22.5% worse than -22.4% | [TLT_2023-01-03_2026-10-12_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/TLT_2023-01-03_2026-10-12_20261012T150155Z.json) |
| GLD IS | 0.38 / 0.57 | -15.6% / -22.0% | 3.8% / 7.4% | 0.026% / 0.032% | 0.49 | 69% | 34 / 34 / 34 | contradicts: Sharpe 0.38 < buy&hold 0.57 + 0.10; return/exposure day 0.026% < buy&hold mean 0.032% + 1bp | [GLD_2016-01-04_2022-12-30_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/GLD_2016-01-04_2022-12-30_20261012T150155Z.json) |
| GLD OOS | 1.07 / 1.18 | -25.5% / -26.4% | 16.5% / 24.1% | 0.103% / 0.094% | 1.36 | 64% | 21 / 20 / 20 | contradicts: Sharpe 1.07 < buy&hold 1.18 + 0.10; return/exposure day 0.103% < buy&hold mean 0.094% + 1bp | [GLD_2023-01-03_2026-10-12_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/GLD_2023-01-03_2026-10-12_20261012T150155Z.json) |
| XLE IS | 0.44 / 0.46 | -64.2% / -66.8% | 8.8% / 10.0% | 0.069% / 0.059% | 0.53 | 71% | 37 / 36 / 36 | contradicts: Sharpe 0.44 < buy&hold 0.46 + 0.10 | [XLE_2016-01-04_2022-12-30_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/XLE_2016-01-04_2022-12-30_20261012T150155Z.json) |
| XLE OOS | 0.70 / 0.74 | -18.8% / -20.1% | 12.4% / 15.1% | 0.080% / 0.066% | 0.87 | 67% | 21 / 20 / 20 | contradicts: Sharpe 0.70 < buy&hold 0.74 + 0.10 | [XLE_2023-01-03_2026-10-12_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/XLE_2023-01-03_2026-10-12_20261012T150155Z.json) |
| EFA IS | 0.20 / 0.35 | -33.4% / -34.2% | 1.9% / 4.8% | 0.020% / 0.026% | 0.25 | 69% | 31 / 30 / 30 | contradicts: Sharpe 0.20 < buy&hold 0.35 + 0.10; return/exposure day 0.020% < buy&hold mean 0.026% + 1bp | [EFA_2016-01-04_2022-12-30_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/EFA_2016-01-04_2022-12-30_20261012T150155Z.json) |
| EFA OOS | 1.26 / 1.08 | -13.1% / -14.1% | 17.1% / 16.2% | 0.100% / 0.064% | 1.58 | 66% | 22 / 21 / 21 | supports: passes kill threshold | [EFA_2023-01-03_2026-10-12_20261012T150155Z.json](../backtests/bollinger_stepaside_v1/EFA_2023-01-03_2026-10-12_20261012T150155Z.json) |

The memo assumed the strategy would be in the market about 90% of days; measured exposure is 64-74%, because the step-aside lasts until the close falls back below the 20-day mean. The rule was tested exactly as written.

---

## Idea B (hypothesis 18): Multi-week 50-day mean reversion, no trend filter

- **Ledger hypothesis id:** 18
- **Strategy file:** `strategies/mean_reversion_z50_v1.py`

### Hypothesis
Going long at the close where z50 = (close - SMA50) / std50 < -1.5 and holding until the first close with z50 >= 0 or 30 trading days, whichever first, with no trend filter, earns at least 5 bps/day more per exposure day than buy-and-hold's daily mean and a conditional Sharpe at least 0.25 above buy-and-hold's Sharpe on GLD/TLT/XLE (and IWM/EFA in the test set).

### Fixed parameters and sources
50-day window: the standard intermediate-trend anchor (Brock, Lakonishok and LeBaron 1992 used 50-day moving averages). -1.5 standard deviations: one step inside the common 2-sigma band, chosen by reasoning so that entries are frequent enough (every cell needs at least 12 IS and 6 OOS entries) while still marking a real stretch. Exit at z50 >= 0 (the mean) and a 30-trading-day cap (about 1.5x the typical half-life of a 50d deviation; the cap bounds the damage of a regime change). New triggers while in a trade are ignored (one trade at a time). None tuned.

### Why it might work
GLD, TLT and XLE are regime-driven rather than carrying a long-run equity-style drift: gold and long bonds are anchored to real-yield and central-bank expectations, XLE to inventory and OPEC supply cycles. A multi-week drop of 1.5 std below the 50d mean is often forced selling (ETF redemptions, hedging unwinds, producers' hedging) that dissipates as fundamentals reassert. Other side: capitulating sellers and trend-chasers, who sell lows to valuation/hedging buyers. Unlike H5-H7, the holding period is weeks, which both amortises the 10 bps round-trip cost over a larger gross edge and raises exposure. No 200d filter: on drift-less assets a "price above SMA200" gate would remove most of the signals and is itself the round-1 exposure problem; this removes the safety net, so the 30-day cap is the safeguard.

### Exact market conditions needed
- Mean-reverting episodes around the 50d mean (range-bound or choppy phases), not a single sustained trend through the whole window. A persistent downtrend (TLT 2022, XLE early 2020) is the adverse regime: z50 stays below the entry and entries pile into a falling price until the cap.
- At least 12 (IS) / 6 (OOS) entries per cell; otherwise inconclusive.
- Fill optimism: entry at the stressed close; the cap exit at 30 days is unaffected.

### How it could fail (decide now)
A cell fails if ANY of: rped < bh_mean + 5 bps; cond_sharpe < bh_sharpe + 0.25; total Sharpe < bh_sharpe - 0.10. Example numbers: if B&H mean is 0.02%/day (5%/yr), rped must be at least 0.07%; if B&H mean is -0.01%, rped must be at least 0.04%. Veto: any cell with rped < -5 bps rejects the hypothesis outright. Placebo metric: **return_per_exposure_day** (the position is out of the market most days, so the placebo must preserve exposure and compare per-day edge).

### Test plan
Same cells and pass rule as the shared section; 5 bps; B&H benchmark.

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/mean_reversion_z50_v1.py`.

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.06 / 0.45 | -42.7% / -41.3% | -0.2% / 8.2% | 0.019% / 0.042% | 0.16 | 21% | 20 / 19 / 19 | contradicts: return/exposure day 0.019% < buy&hold mean 0.042% + 5bps; conditional Sharpe 0.16 < buy&hold 0.45 + 0.25; Sharpe 0.06 < buy&hold 0.45 - 0.10 | [IWM_2016-01-04_2022-12-30_20261012T150155Z.json](../backtests/mean_reversion_z50_v1/IWM_2016-01-04_2022-12-30_20261012T150155Z.json) |
| IWM OOS | 0.23 / 0.76 | -19.1% / -27.5% | 2.0% / 14.6% | 0.047% / 0.062% | 0.51 | 22% | 11 / 10 / 10 | contradicts: return/exposure day 0.047% < buy&hold mean 0.062% + 5bps; conditional Sharpe 0.51 < buy&hold 0.76 + 0.25; Sharpe 0.23 < buy&hold 0.76 - 0.10 | [IWM_2023-01-03_2026-10-12_20261012T150155Z.json](../backtests/mean_reversion_z50_v1/IWM_2023-01-03_2026-10-12_20261012T150155Z.json) |
| TLT IS | -0.37 / 0.03 | -34.2% / -44.1% | -3.5% / -0.7% | -0.041% / 0.002% | -0.63 | 31% | 27 / 27 / 27 | contradicts: return/exposure day -0.041% < buy&hold mean 0.002% + 5bps; conditional Sharpe -0.63 < buy&hold 0.03 + 0.25; Sharpe -0.37 < buy&hold 0.03 - 0.10 | [TLT_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/TLT_2016-01-04_2022-12-30_20261012T150156Z.json) |
| TLT OOS | 0.14 / -0.10 | -13.2% / -22.4% | 0.8% / -2.4% | 0.013% / -0.006% | 0.27 | 38% | 17 / 16 / 16 | contradicts: return/exposure day 0.013% < buy&hold mean -0.006% + 5bps | [TLT_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/TLT_2023-01-03_2026-10-12_20261012T150156Z.json) |
| GLD IS | 0.53 / 0.57 | -11.7% / -22.0% | 3.6% / 7.4% | 0.059% / 0.032% | 1.10 | 25% | 24 / 24 / 24 | contradicts: return/exposure day 0.059% < buy&hold mean 0.032% + 5bps | [GLD_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/GLD_2016-01-04_2022-12-30_20261012T150156Z.json) |
| GLD OOS | -0.02 / 1.18 | -16.9% / -26.4% | -0.5% / 24.1% | -0.006% / 0.094% | -0.03 | 13% | 7 / 7 / 7 | contradicts: return/exposure day -0.006% < buy&hold mean 0.094% + 5bps; conditional Sharpe -0.03 < buy&hold 1.18 + 0.25; Sharpe -0.02 < buy&hold 1.18 - 0.10 | [GLD_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/GLD_2023-01-03_2026-10-12_20261012T150156Z.json) |
| XLE IS | 0.14 / 0.46 | -55.3% / -66.8% | 0.7% / 10.0% | 0.045% / 0.059% | 0.29 | 27% | 22 / 22 / 22 | contradicts: return/exposure day 0.045% < buy&hold mean 0.059% + 5bps; conditional Sharpe 0.29 < buy&hold 0.46 + 0.25; Sharpe 0.14 < buy&hold 0.46 - 0.10 | [XLE_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/XLE_2016-01-04_2022-12-30_20261012T150156Z.json) |
| XLE OOS | 1.07 / 0.74 | -11.8% / -20.1% | 12.4% / 15.1% | 0.225% / 0.066% | 2.33 | 22% | 12 / 12 / 12 | supports: passes kill threshold | [XLE_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/XLE_2023-01-03_2026-10-12_20261012T150156Z.json) |
| EFA IS | 0.29 / 0.35 | -29.1% / -34.2% | 3.0% / 4.8% | 0.066% / 0.026% | 0.64 | 23% | 24 / 24 / 24 | contradicts: return/exposure day 0.066% < buy&hold mean 0.026% + 5bps | [EFA_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/EFA_2016-01-04_2022-12-30_20261012T150156Z.json) |
| EFA OOS | 1.08 / 1.08 | -8.2% / -14.1% | 8.7% / 16.2% | 0.196% / 0.064% | 2.63 | 18% | 11 / 10 / 10 | supports: passes kill threshold | [EFA_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/mean_reversion_z50_v1/EFA_2023-01-03_2026-10-12_20261012T150156Z.json) |

---

## Idea C (hypothesis 19): High-volume liquidity-shock reversal, 5-day hold

- **Ledger hypothesis id:** 19
- **Strategy file:** `strategies/volume_shock_reversal_v1.py`

### Hypothesis
Going long at the close of a day where the 3-day return divided by (sd20 x sqrt(3)) is below -1.25 AND volume exceeds 1.25 times the mean of the previous 20 days' volume, then holding exactly 5 trading days, earns at least 5 bps/day more per exposure day than buy-and-hold's daily mean and a conditional Sharpe at least 0.25 above buy-and-hold's.

### Fixed parameters and sources
- r3 = close_t / close_{t-3} - 1; sd20 = sample std (ddof=1) of the 20 daily returns ending at t-1 (excludes today, so no look-ahead); volume ratio = volume_t / mean(volume over the 20 days ending t-1).
- Volume threshold 1.25 and z threshold -1.25: chosen by reasoning for sufficient trade count (at least 20 IS and 10 OOS entries per cell, otherwise inconclusive), deliberately milder than typical "2x volume" screens to avoid a data-starved test. Not tuned.
- 5-day hold: reversal after liquidity shocks is documented to play out within about a week (Campbell, Grossman and Wang 1993; weekly reversal literature). New triggers during a hold are ignored.

### Why it might work
Campbell, Grossman and Wang (1993): price drops on high volume reflect liquidity demand (inventory transfer to market makers, who demand compensation), so they partly reverse; drops on low volume are information-driven and tend to continue. Other side: forced sellers (redemptions, margin calls, stop cascades) paying a liquidity premium to dealers. GLD, TLT and XLE experience flow-driven volume spikes (ETF creation/redemption, macro de-risking). Difference from H6 (down closes) and H7 (close location): the trigger needs volume confirmation, and the size is volatility-scaled so a "big drop" has the same meaning in IWM and TLT.

### Exact market conditions needed
- Liquidity-driven selling spikes in the asset; the strategy needs volume to be informative, so it fails in assets/periods where heavy volume signals news-driven repricing (e.g. XLE in an oil collapse, TLT in a rate shock).
- Exposure is expected only 3-8% of days, so entries are the binding constraint: at least 20 (IS) / 10 (OOS) or the cell is inconclusive. If more than 2 of the 5 symbols are inconclusive in a window the hypothesis cannot reach 4/5 and the round script reports it as untestable rather than rejecting it; it would then need a longer sample, not a looser threshold.
- Fill optimism is largest here: the entry is the stressed close, and the signal needs the full-day volume, so a real MOC order would be sized before volume is final (approximate with the 15:50 snapshot); expect real-world slippage beyond 5 bps. Gross edge must exceed about 10 bps round trip to be worth anything.

### How it could fail (decide now)
A cell fails if ANY of: rped < bh_mean + 5 bps; cond_sharpe < bh_sharpe + 0.25; total Sharpe < bh_sharpe - 0.10. Veto: any cell with rped < -5 bps rejects the hypothesis. Placebo metric: **return_per_exposure_day**. Because few entries make placebo percentiles noisy, a passing cell with fewer than 30 entries (both windows pooled) still counts, but the mean-percentile rule of 0.95 applies as stated.

### Test plan
Same cells and pass rule as the shared section; 5 bps; B&H benchmark.

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/volume_shock_reversal_v1.py`.

Notes: veto: GLD IS: return/exposure day -0.054% below -5bps; XLE OOS: return/exposure day -0.097% below -5bps; EFA IS: return/exposure day -0.077% below -5bps

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.16 / 0.45 | -37.9% / -41.3% | 1.2% / 8.2% | 0.050% / 0.042% | 0.47 | 16% | 57 / 57 / 57 | contradicts: return/exposure day 0.050% < buy&hold mean 0.042% + 5bps; conditional Sharpe 0.47 < buy&hold 0.45 + 0.25; Sharpe 0.16 < buy&hold 0.45 - 0.10 | [IWM_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/IWM_2016-01-04_2022-12-30_20261012T150156Z.json) |
| IWM OOS | 0.29 / 0.76 | -12.9% / -27.5% | 2.3% / 14.6% | 0.072% / 0.062% | 0.88 | 14% | 28 / 27 / 27 | contradicts: return/exposure day 0.072% < buy&hold mean 0.062% + 5bps; conditional Sharpe 0.88 < buy&hold 0.76 + 0.25; Sharpe 0.29 < buy&hold 0.76 - 0.10 | [IWM_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/IWM_2023-01-03_2026-10-12_20261012T150156Z.json) |
| TLT IS | -0.19 / 0.03 | -17.2% / -44.1% | -1.6% / -0.7% | -0.035% / 0.002% | -0.34 | 15% | 53 / 53 / 53 | contradicts: return/exposure day -0.035% < buy&hold mean 0.002% + 5bps; conditional Sharpe -0.34 < buy&hold 0.03 + 0.25; Sharpe -0.19 < buy&hold 0.03 - 0.10 | [TLT_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/TLT_2016-01-04_2022-12-30_20261012T150156Z.json) |
| TLT OOS | -0.02 / -0.10 | -9.8% / -22.4% | -0.3% / -2.4% | -0.003% / -0.006% | 0.12 | 16% | 30 / 30 / 30 | contradicts: return/exposure day -0.003% < buy&hold mean -0.006% + 5bps; conditional Sharpe 0.12 < buy&hold -0.10 + 0.25 | [TLT_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/TLT_2023-01-03_2026-10-12_20261012T150156Z.json) |
| GLD IS | -0.30 / 0.57 | -19.0% / -22.0% | -1.9% / 7.4% | -0.054% / 0.032% | -0.69 | 13% | 45 / 45 / 45 | contradicts: return/exposure day -0.054% < buy&hold mean 0.032% + 5bps; conditional Sharpe -0.69 < buy&hold 0.57 + 0.25; Sharpe -0.30 < buy&hold 0.57 - 0.10 | [GLD_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/GLD_2016-01-04_2022-12-30_20261012T150156Z.json) |
| GLD OOS | 0.08 / 1.18 | -12.2% / -26.4% | 0.3% / 24.1% | 0.026% / 0.094% | 0.34 | 10% | 18 / 18 / 18 | contradicts: return/exposure day 0.026% < buy&hold mean 0.094% + 5bps; conditional Sharpe 0.34 < buy&hold 1.18 + 0.25; Sharpe 0.08 < buy&hold 1.18 - 0.10 | [GLD_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/GLD_2023-01-03_2026-10-12_20261012T150156Z.json) |
| XLE IS | 0.12 / 0.46 | -51.1% / -66.8% | 0.6% / 10.0% | 0.054% / 0.059% | 0.38 | 14% | 50 / 50 / 50 | contradicts: return/exposure day 0.054% < buy&hold mean 0.059% + 5bps; conditional Sharpe 0.38 < buy&hold 0.46 + 0.25; Sharpe 0.12 < buy&hold 0.46 - 0.10 | [XLE_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/XLE_2016-01-04_2022-12-30_20261012T150156Z.json) |
| XLE OOS | -0.32 / 0.74 | -16.6% / -20.1% | -3.8% / 15.1% | -0.097% / 0.066% | -0.78 | 14% | 26 / 26 / 26 | contradicts: return/exposure day -0.097% < buy&hold mean 0.066% + 5bps; conditional Sharpe -0.78 < buy&hold 0.74 + 0.25; Sharpe -0.32 < buy&hold 0.74 - 0.10 | [XLE_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/XLE_2023-01-03_2026-10-12_20261012T150156Z.json) |
| EFA IS | -0.29 / 0.35 | -25.8% / -34.2% | -3.4% / 4.8% | -0.077% / 0.026% | -0.66 | 15% | 53 / 53 / 53 | contradicts: return/exposure day -0.077% < buy&hold mean 0.026% + 5bps; conditional Sharpe -0.66 < buy&hold 0.35 + 0.25; Sharpe -0.29 < buy&hold 0.35 - 0.10 | [EFA_2016-01-04_2022-12-30_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/EFA_2016-01-04_2022-12-30_20261012T150156Z.json) |
| EFA OOS | 0.54 / 1.08 | -5.0% / -14.1% | 3.9% / 16.2% | 0.115% / 0.064% | 1.56 | 14% | 27 / 27 / 27 | contradicts: Sharpe 0.54 < buy&hold 1.08 - 0.10 | [EFA_2023-01-03_2026-10-12_20261012T150156Z.json](../backtests/volume_shock_reversal_v1/EFA_2023-01-03_2026-10-12_20261012T150156Z.json) |

---

## What I deliberately left out
- Post-gap fade: with fills at the signal day's close, day t's gap is already in the past when the signal fires, so it collapses into an IBS-style close-location idea (H7, rejected).
- Sector-versus-market reversion: not allowed (single-symbol input).
- RSI(2), three-down-closes and IBS on these symbols with round-1 parameters: explicitly excluded.
