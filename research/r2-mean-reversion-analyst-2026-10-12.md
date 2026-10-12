# Round 2 mean reversion: three ideas on IWM, TLT, GLD, XLE, EFA

- **Date:** 2026-10-12
- **Analyst:** mean-reversion-analyst (round 2)
- **Ledger hypothesis ids:** 17 (A), 18 (B), 19 (C)
- **Strategy file:** TBD

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
- **Strategy file:** TBD

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
TBD

---

## Idea B (hypothesis 18): Multi-week 50-day mean reversion, no trend filter

- **Ledger hypothesis id:** 18
- **Strategy file:** TBD

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
TBD

---

## Idea C (hypothesis 19): High-volume liquidity-shock reversal, 5-day hold

- **Ledger hypothesis id:** 19
- **Strategy file:** TBD

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
TBD

---

## What I deliberately left out
- Post-gap fade: with fills at the signal day's close, day t's gap is already in the past when the signal fires, so it collapses into an IBS-style close-location idea (H7, rejected).
- Sector-versus-market reversion: not allowed (single-symbol input).
- RSI(2), three-down-closes and IBS on these symbols with round-1 parameters: explicitly excluded.
