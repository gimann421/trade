# Round 2 trend/drawdown hybrids (trend-drawdown-analyst)

- **Date:** 2026-10-12
- **Ledger hypothesis ids:** 14, 15, 16 (all 'proposed')
- **Strategy file:** `strategies/dd_gated_sma_exit_v1.py` (H14), `strategies/trend_vol_throttle_v1.py` (H15), `strategies/cppi_cushion_v1.py` (H16)

Markets: IWM, TLT, GLD, XLE, EFA daily bars (2,710 rows each, 2016-01-04..2026-10-12). SPY/QQQ excluded.
No returns were computed and no parameter was tuned on data; every number below is fixed from the cited source or from reasoning.

## Why round 1's de-risking missed Sharpe, and what this round changes
Ledger H2, H3, H8, H10 (and H1/H4) cut drawdowns by 5-20 points but landed within ~0.01-0.15 Sharpe of buy-and-hold, mostly failing OOS. Two mechanisms, read from the evidence summaries: (a) the rule fires in ordinary dips that recover, so the strategy pays lag and whipsaw for nothing (H8 22 entries, H10 41); (b) it moves all-or-nothing or moves in high-vol uptrends (H2 exposure 78-86%), giving up the upside that produces buy-and-hold's Sharpe. Every idea below therefore (1) requires two different stress signals to agree before cutting (trend AND drawdown, or trend AND vol), so shallow recoveries leave it fully invested; (2) cuts in fractional steps with a floor above zero until damage is deep; (3) is asymmetric, slow to re-risk. This is a hypothesis about fewer false cuts, not a guarantee; the kill rules below are meant to bite.

Not repeats: no SMA 50/200 cross (H1), no always-on vol scaling (H2), no multi-horizon sign ladder (H3), no channel breakout (H4), no vol-ratio switch (H8), no range-shock timeout (H10). Vol or SMA appear only as conditions inside different rule structures.

## Common test protocol (applies to all three ideas)
- Costs/benchmark: 5 bps per unit turnover per core/backtest.py; benchmark buy-and-hold on the same symbol, 5 bps. Fractional weights are quantized to a 0.25 grid so daily rebalancing churn is limited to 0.25 x 5 bps = 1.25 bps per step; total cost is reported per cell.
- Windows: IS 2016-01-01..2022-12-31, OOS 2023-01-01..end; signals on full history, then sliced. Weight 1 during indicator warmup (SMA200/252d high need ~252 rows, so most of 2016 is warmup).
- Cell kill rule (identical for all ideas, codable): cell passes iff Sharpe_s >= 1.0 x Sharpe_bh AND (MaxDD_s - MaxDD_bh) >= min(0.05, 0.25 x |MaxDD_bh|), i.e. core.verdicts.drawdown_rule(r, dd_margin=min(0.05, 0.25*abs(r["buy_and_hold"]["max_drawdown"])), sharpe_mult=1.0). Using multiplier 1.0 keeps the Sharpe test meaningful when buy-and-hold Sharpe is negative (a multiple of a negative number would flip the test).
- TLT/GLD handling: where buy-and-hold is flat or weak, the drawdown margin shrinks to 25% of its own drawdown when that is under 5 points, so a shallow benchmark drawdown is not impossible to beat. Because a weak benchmark makes passing easy (merely being out helps), at least 3 of the passing symbols must have buy-and-hold Sharpe > 0 in both windows.
- Minimum events: a de-risk event is a day-on-day weight drop >= 0.25. A cell with fewer than 3 events (IS) or 2 events (OOS) is inconclusive (it cannot pass, and is not counted as contradicting).
- Cross-market rule: SUPPORTED only if core.verdicts.symbol_status(cells, min_symbols=4) == "supported".
- Placebo: metric = sharpe (positions are fractional and almost always > 0, so return_per_exposure_day is uninformative). placebo_percentile(asset, position, cost_bps=5, metric="sharpe", n=1000, seed=0, min_shift=252) per passing cell; pooled = mean over all passing cells; must be >= 0.95.
- No-big-failure rule: if any cell on any symbol (including non-passing symbols) has Sharpe_s < Sharpe_bh - 0.15 or MaxDD more than 0.02 deeper than buy-and-hold, the hypothesis is rejected even if 4/5 symbols pass.
- Wrong if any of the above fails. Also reported (not decisive): fraction of days at weight < 1 per cell.

---

## Idea 1 (H14): Drawdown-gated SMA200 stepped exit with slow re-entry
- **Ledger hypothesis id:** 14
- **Strategy file:** `strategies/dd_gated_sma_exit_v1.py`

### Hypothesis
Weight s in {1, 0.5, 0}, starting at 1. With c = close, S = 200-day SMA of closes, H = 252-day rolling max of closes, DD = c/H - 1, update daily: if c < S and DD <= -0.20 then s = 0; elif c < S and DD <= -0.10 then s = min(s, 0.5); elif c > S and s == 0 then s = 0.5; elif c > S and s == 0.5 and DD > -0.05 then s = 1; else s unchanged. Target weight = s (held over next day). On IWM, TLT, GLD, XLE, EFA it matches or beats buy-and-hold Sharpe and has a drawdown shallower by min(5 pts, 25% of benchmark drawdown) in both windows on >= 4 of 5 symbols.

### Why it might work
Other side: benchmark-style holders who ride a slow bear market and sellers of rallies into strength. Faber (2007) 10-month trend filter reduces deep drawdowns; George and Hwang (2004) find the distance from the 52-week high predicts continuation. The conjunction means shallow dips under the SMA (the false positives that cost round-1 Sharpe) never cut exposure; the 0.5 first step keeps half the upside on a false alarm; re-entry is slow (needs trend and within 5% of high) so there is no sawtooth. Parameters: SMA200 (Faber), -10%/-20% (conventional correction/bear-market thresholds), -5% (half the first threshold).

### Exact market conditions needed
Persistent multi-month declines, not V-shaped crashes: 2022 (TLT, IWM, EFA, GLD H2 2022-early 2023), XLE 2020, GLD 2021-22, IWM 2018Q4-2020 (partly). It will lose to V recoveries such as spring 2020 and Q1 2025 (late to re-enter). Needs at least a few such episodes per symbol; XLE and TLT have them, GLD's 2023-26 uptrend may produce zero events (then inconclusive).

### How it could fail (numeric)
Any of the common protocol failures: fewer than 4 of 5 symbols passing both windows; mean placebo percentile < 0.95; Sharpe below buy-and-hold - 0.15 on any cell; drawdown deeper than buy-and-hold by > 2 points on any cell. Also if the filter is a no-op (weight < 1 on fewer than 5% of days) in 3+ cells the idea is untestable and reported inconclusive.

### Test plan
Per common protocol. 10 cells (5 symbols x 2 windows).

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/dd_gated_sma_exit_v1.py`.

Notes: veto: IWM OOS: Sharpe 0.50 more than 0.15 below buy&hold 0.76; TLT OOS: Sharpe -0.70 more than 0.15 below buy&hold -0.10; GLD IS: Sharpe 0.42 more than 0.15 below buy&hold 0.57; XLE OOS: Sharpe 0.37 more than 0.15 below buy&hold 0.74; EFA OOS: Sharpe 0.86 more than 0.15 below buy&hold 1.08

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.52 / 0.45 | -27.4% / -41.3% | 6.7% / 8.2% | 0.036% / 0.042% | 0.58 | 72% | 7 / 7 / 10 | supports: passes kill threshold | [IWM_2016-01-04_2022-12-30_20261012T150152Z.json](../backtests/dd_gated_sma_exit_v1/IWM_2016-01-04_2022-12-30_20261012T150152Z.json) |
| IWM OOS | 0.50 / 0.76 | -16.6% / -27.5% | 7.1% / 14.6% | 0.035% / 0.062% | 0.52 | 80% | 2 / 1 / 4 | contradicts: Sharpe 0.50 < 1x buy&hold 0.76 | [IWM_2023-01-03_2026-10-12_20261012T150152Z.json](../backtests/dd_gated_sma_exit_v1/IWM_2023-01-03_2026-10-12_20261012T150152Z.json) |
| TLT IS | 0.14 / 0.03 | -26.1% / -44.1% | 1.0% / -0.7% | 0.008% / 0.002% | 0.16 | 74% | 2 / 2 / 6 | supports: passes kill threshold | [TLT_2016-01-04_2022-12-30_20261012T150152Z.json](../backtests/dd_gated_sma_exit_v1/TLT_2016-01-04_2022-12-30_20261012T150152Z.json) |
| TLT OOS | -0.70 / -0.10 | -21.8% / -22.4% | -6.0% / -2.4% | -0.026% / -0.006% | -0.74 | 63% | 3 / 2 / 5 | contradicts: Sharpe -0.70 < 1x buy&hold -0.10; MaxDD -21.8% not 5pts better than -22.4% | [TLT_2023-01-03_2026-10-12_20261012T150152Z.json](../backtests/dd_gated_sma_exit_v1/TLT_2023-01-03_2026-10-12_20261012T150152Z.json) |
| GLD IS | 0.42 / 0.57 | -18.7% / -22.0% | 4.4% / 7.4% | 0.021% / 0.032% | 0.43 | 79% | 2 / 1 / 6 | contradicts: Sharpe 0.42 < 1x buy&hold 0.57; MaxDD -18.7% not 5pts better than -22.0% | [GLD_2016-01-04_2022-12-30_20261012T150152Z.json](../backtests/dd_gated_sma_exit_v1/GLD_2016-01-04_2022-12-30_20261012T150152Z.json) |
| GLD OOS | 1.20 / 1.18 | -21.8% / -26.4% | 22.6% / 24.1% | 0.095% / 0.094% | 1.25 | 88% | 2 / 2 / 3 | contradicts: MaxDD -21.8% not 5pts better than -26.4% | [GLD_2023-01-03_2026-10-12_20261012T150152Z.json](../backtests/dd_gated_sma_exit_v1/GLD_2023-01-03_2026-10-12_20261012T150152Z.json) |
| XLE IS | 0.46 / 0.46 | -32.6% / -66.8% | 7.6% / 10.0% | 0.048% / 0.059% | 0.53 | 64% | 8 / 7 / 11 | supports: passes kill threshold | [XLE_2016-01-04_2022-12-30_20261012T150153Z.json](../backtests/dd_gated_sma_exit_v1/XLE_2016-01-04_2022-12-30_20261012T150153Z.json) |
| XLE OOS | 0.37 / 0.74 | -29.3% / -20.1% | 5.3% / 15.1% | 0.029% / 0.066% | 0.38 | 79% | 2 / 1 / 7 | contradicts: Sharpe 0.37 < 1x buy&hold 0.74; MaxDD -29.3% not 5pts better than -20.1% | [XLE_2023-01-03_2026-10-12_20261012T150153Z.json](../backtests/dd_gated_sma_exit_v1/XLE_2023-01-03_2026-10-12_20261012T150153Z.json) |
| EFA IS | 0.28 / 0.35 | -24.3% / -34.2% | 2.7% / 4.8% | 0.015% / 0.026% | 0.30 | 78% | 4 / 3 / 6 | contradicts: Sharpe 0.28 < 1x buy&hold 0.35 | [EFA_2016-01-04_2022-12-30_20261012T150153Z.json](../backtests/dd_gated_sma_exit_v1/EFA_2016-01-04_2022-12-30_20261012T150153Z.json) |
| EFA OOS | 0.86 / 1.08 | -13.7% / -14.1% | 11.8% / 16.2% | 0.048% / 0.064% | 0.86 | 97% | 1 / 0 / 3 | contradicts: Sharpe 0.86 < 1x buy&hold 1.08; MaxDD -13.7% not 3.51388pts better than -14.1% | [EFA_2023-01-03_2026-10-12_20261012T150153Z.json](../backtests/dd_gated_sma_exit_v1/EFA_2023-01-03_2026-10-12_20261012T150153Z.json) |

---

## Idea 2 (H15): Trend-conditioned volatility throttle (vol ignored in uptrends)
- **Ledger hypothesis id:** 15
- **Strategy file:** `strategies/trend_vol_throttle_v1.py`

### Hypothesis
Regime flag D (downtrend): turns on when close < 200d SMA, turns off only when close > 1.02 x 200d SMA (weight 1 in warmup). When D is off weight = 1. When D is on, weight = floor to the 0.25 grid of min(0.5, 0.10 / sigma), sigma = 63-day standard deviation of daily log returns x sqrt(252), so weight in {0.5, 0.25, 0} (0 when sigma > 40%). Meets the common cell kill rule on >= 4 of 5 symbols in both windows.

### Why it might work
Other side: holders who keep full risk in a confirmed downtrend, and low-vol-seeking buyers who stay out of high-vol uptrends. Volatility is high mainly in downtrends and low in uptrends (leverage effect), and Moreira and Muir (2017) show vol-managed exposure improves Sharpe; H2's shortfall (see ledger: exposure 78-86%, Sharpe 1.42 vs 1.43, 1.48 vs 1.51 OOS) is consistent with throttling on high-vol days within uptrends and paying for it. Here vol only sizes exposure after the trend has failed, so uptrends keep 100% exposure, and the 2% re-entry band (asymmetric: instant exit, confirmed return) reduces SMA sawtooth turnover. The 10% target is two thirds of H2's 15%, chosen by reasoning because this applies only in the weak regime; 63 days and SMA200 are standard windows.

### Exact market conditions needed
Downtrend regimes where vol is high and returns are negative (2022 for TLT/IWM/EFA, XLE 2020, GLD 2021-22); needs the downtrend to last long enough to exceed a handful of days. It fails in downtrends that are high-vol but recover quickly (April 2025 style) or in low-vol grinding declines (TLT 2022 had moderate vol so weight stays 0.5, which limits the drawdown cut).

### How it could fail (numeric)
Common protocol failures (fewer than 4 of 5 symbols passing both windows; mean placebo percentile < 0.95; any cell Sharpe < buy-and-hold - 0.15; any cell drawdown > 2 points deeper). Additional: if the max weight of 0.5 in downtrends cannot reach the drawdown margin in 3+ cells with at least 3 events (IS) / 2 (OOS), that is a design failure to record rather than a reason to retune.

### Test plan
Per common protocol.

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/trend_vol_throttle_v1.py`.

Notes: veto: IWM OOS: Sharpe 0.59 more than 0.15 below buy&hold 0.76; TLT OOS: Sharpe -0.63 more than 0.15 below buy&hold -0.10; XLE OOS: Sharpe 0.41 more than 0.15 below buy&hold 0.74

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.47 / 0.45 | -28.8% / -41.3% | 6.1% / 8.2% | 0.029% / 0.042% | 0.48 | 75% | 3 / 2 / 19 | supports: passes kill threshold | [IWM_2016-01-04_2022-12-30_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/IWM_2016-01-04_2022-12-30_20261012T150153Z.json) |
| IWM OOS | 0.59 / 0.76 | -17.8% / -27.5% | 9.2% / 14.6% | 0.041% / 0.062% | 0.59 | 85% | 1 / 0 / 9 | contradicts: Sharpe 0.59 < 1x buy&hold 0.76 | [IWM_2023-01-03_2026-10-12_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/IWM_2023-01-03_2026-10-12_20261012T150153Z.json) |
| TLT IS | 0.26 / 0.03 | -28.4% / -44.1% | 2.4% / -0.7% | 0.012% / 0.002% | 0.26 | 74% | 1 / 0 / 13 | supports: passes kill threshold | [TLT_2016-01-04_2022-12-30_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/TLT_2016-01-04_2022-12-30_20261012T150153Z.json) |
| TLT OOS | -0.63 / -0.10 | -24.2% / -22.4% | -5.9% / -2.4% | -0.022% / -0.006% | -0.63 | 63% | 1 / 0 / 17 | contradicts: Sharpe -0.63 < 1x buy&hold -0.10; MaxDD -24.2% not 5pts better than -22.4% | [TLT_2023-01-03_2026-10-12_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/TLT_2023-01-03_2026-10-12_20261012T150153Z.json) |
| GLD IS | 0.44 / 0.57 | -22.3% / -22.0% | 4.8% / 7.4% | 0.021% / 0.032% | 0.44 | 78% | 1 / 0 / 14 | contradicts: Sharpe 0.44 < 1x buy&hold 0.57; MaxDD -22.3% not 5pts better than -22.0% | [GLD_2016-01-04_2022-12-30_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/GLD_2016-01-04_2022-12-30_20261012T150153Z.json) |
| GLD OOS | 1.21 / 1.18 | -23.1% / -26.4% | 23.1% / 24.1% | 0.089% / 0.094% | 1.21 | 91% | 1 / 0 / 4 | contradicts: MaxDD -23.1% not 5pts better than -26.4% | [GLD_2023-01-03_2026-10-12_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/GLD_2023-01-03_2026-10-12_20261012T150153Z.json) |
| XLE IS | 0.62 / 0.46 | -36.1% / -66.8% | 11.9% / 10.0% | 0.059% / 0.059% | 0.65 | 73% | 3 / 2 / 16 | supports: passes kill threshold | [XLE_2016-01-04_2022-12-30_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/XLE_2016-01-04_2022-12-30_20261012T150153Z.json) |
| XLE OOS | 0.41 / 0.74 | -25.1% / -20.1% | 6.0% / 15.1% | 0.030% / 0.066% | 0.41 | 79% | 1 / 0 / 17 | contradicts: Sharpe 0.41 < 1x buy&hold 0.74; MaxDD -25.1% not 5pts better than -20.1% | [XLE_2023-01-03_2026-10-12_20261012T150153Z.json](../backtests/trend_vol_throttle_v1/XLE_2023-01-03_2026-10-12_20261012T150153Z.json) |
| EFA IS | 0.22 / 0.35 | -27.8% / -34.2% | 1.9% / 4.8% | 0.011% / 0.026% | 0.22 | 78% | 3 / 2 / 14 | contradicts: Sharpe 0.22 < 1x buy&hold 0.35 | [EFA_2016-01-04_2022-12-30_20261012T150154Z.json](../backtests/trend_vol_throttle_v1/EFA_2016-01-04_2022-12-30_20261012T150154Z.json) |
| EFA OOS | 0.97 / 1.08 | -12.5% / -14.1% | 13.3% / 16.2% | 0.053% / 0.064% | 0.97 | 94% | 1 / 0 / 3 | contradicts: Sharpe 0.97 < 1x buy&hold 1.08; MaxDD -12.5% not 3.51388pts better than -14.1% | [EFA_2023-01-03_2026-10-12_20261012T150154Z.json](../backtests/trend_vol_throttle_v1/EFA_2023-01-03_2026-10-12_20261012T150154Z.json) |

---

## Idea 3 (H16): CPPI-style drawdown cushion with trend-gated re-risking
- **Ledger hypothesis id:** 16
- **Strategy file:** `strategies/cppi_cushion_v1.py`

### Hypothesis
With H = 252-day rolling max of closes, floor F = 0.70 x H, cushion c = (close - F)/close, target w* = floor to the 0.25 grid of min(1, 4 x c) (0 if c <= 0). Weight w_t = w*_t when w*_t <= w_{t-1} (reductions immediately), and when w*_t > w_{t-1} only if close > 100-day SMA, in which case w_t = w*_t; otherwise w_t = w_{t-1} (weight 1 in warmup). Meets the common cell kill rule on >= 4 of 5 symbols in both windows.

### Why it might work
Other side: constant-exposure/dip-buying holders who rebalance back up after losses. CPPI (Perold and Sharpe 1988; Black and Perold 1992) scales risk with the cushion above a floor, a long-convex payoff that cuts risk progressively as a drawdown deepens. Its known weakness is lagging V-recoveries; gating increases on close > 100-day SMA (a trend condition, the fixed 5-month window sits within the 3-12 month time-series momentum range) prevents buying back into bounces. First cut occurs ~6.7% under the high and weight is zero at -28.6% (c = 0 at -30%); the multiplier 4 and floor 70% come from published CPPI ranges (multiplier 3-6) and a 30% loss budget. Cost: 1.25 bps per 0.25 step; Sharpe depends on timing, not fees. Related to Idea 1 (shared 252d-high variable), so outcomes are expected to correlate; it differs by being continuous and by gating only re-risking.

### Exact market conditions needed
Drawdowns that progress gradually (stepwise deleveraging beats a binary rule) and recoveries that are trend-confirmed rather than sudden. Hurts in V-shaped sell-offs (2020, 2025) and in assets repeatedly oscillating 7-12% below highs (GLD, XLE sideways spells), where it will be under-invested for little benefit.

### How it could fail (numeric)
Same common protocol failures. In particular a mean time at weight < 1 above 40% of days in any window with Sharpe below buy-and-hold on 3+ symbols counts as the cushion being too tight, recorded as failure of the idea, not retuned.

### Test plan
Per common protocol.

### Results

**Verdict: rejected** (round 2, 2026-10-12; rules fixed before testing, scored by `research/round2_verdicts.py`). Strategy: `strategies/cppi_cushion_v1.py`.

Notes: veto: IWM OOS: Sharpe 0.51 more than 0.15 below buy&hold 0.76; TLT OOS: Sharpe -0.60 more than 0.15 below buy&hold -0.10; XLE OOS: Sharpe 0.35 more than 0.15 below buy&hold 0.74; EFA OOS: Sharpe 0.92 more than 0.15 below buy&hold 1.08

| Cell | Sharpe (strat / B&H) | Max DD (strat / B&H) | CAGR (strat / B&H) | Return per exposure day (strat / B&H mean) | Cond. Sharpe | Exposure | Entries / exits / de-risk events | Verdict | Backtest |
|---|---|---|---|---|---|---|---|---|---|
| IWM IS | 0.37 / 0.45 | -29.8% / -41.3% | 4.5% / 8.2% | 0.024% / 0.042% | 0.39 | 77% | 8 / 7 / 40 | contradicts: Sharpe 0.37 < 1x buy&hold 0.45 | [IWM_2016-01-04_2022-12-30_20261012T150154Z.json](../backtests/cppi_cushion_v1/IWM_2016-01-04_2022-12-30_20261012T150154Z.json) |
| IWM OOS | 0.51 / 0.76 | -21.3% / -27.5% | 7.4% / 14.6% | 0.035% / 0.062% | 0.52 | 84% | 2 / 1 / 31 | contradicts: Sharpe 0.51 < 1x buy&hold 0.76 | [IWM_2023-01-03_2026-10-12_20261012T150154Z.json](../backtests/cppi_cushion_v1/IWM_2023-01-03_2026-10-12_20261012T150154Z.json) |
| TLT IS | 0.11 / 0.03 | -28.6% / -44.1% | 0.6% / -0.7% | 0.005% / 0.002% | 0.11 | 76% | 2 / 2 / 28 | supports: passes kill threshold | [TLT_2016-01-04_2022-12-30_20261012T150154Z.json](../backtests/cppi_cushion_v1/TLT_2016-01-04_2022-12-30_20261012T150154Z.json) |
| TLT OOS | -0.60 / -0.10 | -22.9% / -22.4% | -6.1% / -2.4% | -0.024% / -0.006% | -0.60 | 72% | 3 / 2 / 24 | contradicts: Sharpe -0.60 < 1x buy&hold -0.10; MaxDD -22.9% not 5pts better than -22.4% | [TLT_2023-01-03_2026-10-12_20261012T150154Z.json](../backtests/cppi_cushion_v1/TLT_2023-01-03_2026-10-12_20261012T150154Z.json) |
| GLD IS | 0.47 / 0.57 | -21.1% / -22.0% | 5.3% / 7.4% | 0.023% / 0.032% | 0.47 | 85% | 1 / 0 / 23 | contradicts: Sharpe 0.47 < 1x buy&hold 0.57; MaxDD -21.1% not 5pts better than -22.0% | [GLD_2016-01-04_2022-12-30_20261012T150154Z.json](../backtests/cppi_cushion_v1/GLD_2016-01-04_2022-12-30_20261012T150154Z.json) |
| GLD OOS | 1.27 / 1.18 | -23.1% / -26.4% | 22.7% / 24.1% | 0.090% / 0.094% | 1.30 | 87% | 2 / 1 / 22 | contradicts: MaxDD -23.1% not 5pts better than -26.4% | [GLD_2023-01-03_2026-10-12_20261012T150154Z.json](../backtests/cppi_cushion_v1/GLD_2023-01-03_2026-10-12_20261012T150154Z.json) |
| XLE IS | 0.34 / 0.46 | -39.4% / -66.8% | 4.7% / 10.0% | 0.030% / 0.059% | 0.37 | 64% | 7 / 6 / 61 | contradicts: Sharpe 0.34 < 1x buy&hold 0.46 | [XLE_2016-01-04_2022-12-30_20261012T150154Z.json](../backtests/cppi_cushion_v1/XLE_2016-01-04_2022-12-30_20261012T150154Z.json) |
| XLE OOS | 0.35 / 0.74 | -23.7% / -20.1% | 4.8% / 15.1% | 0.025% / 0.066% | 0.35 | 83% | 1 / 0 / 52 | contradicts: Sharpe 0.35 < 1x buy&hold 0.74; MaxDD -23.7% not 5pts better than -20.1% | [XLE_2023-01-03_2026-10-12_20261012T150154Z.json](../backtests/cppi_cushion_v1/XLE_2023-01-03_2026-10-12_20261012T150154Z.json) |
| EFA IS | 0.20 / 0.35 | -24.7% / -34.2% | 1.8% / 4.8% | 0.011% / 0.026% | 0.21 | 82% | 3 / 2 / 38 | contradicts: Sharpe 0.20 < 1x buy&hold 0.35 | [EFA_2016-01-04_2022-12-30_20261012T150154Z.json](../backtests/cppi_cushion_v1/EFA_2016-01-04_2022-12-30_20261012T150154Z.json) |
| EFA OOS | 0.92 / 1.08 | -13.5% / -14.1% | 12.5% / 16.2% | 0.050% / 0.064% | 0.92 | 96% | 1 / 0 / 11 | contradicts: Sharpe 0.92 < 1x buy&hold 1.08; MaxDD -13.5% not 3.51388pts better than -14.1% | [EFA_2023-01-03_2026-10-12_20261012T150155Z.json](../backtests/cppi_cushion_v1/EFA_2023-01-03_2026-10-12_20261012T150155Z.json) |
