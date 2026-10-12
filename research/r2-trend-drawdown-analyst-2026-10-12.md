# Round 2 trend/drawdown hybrids (trend-drawdown-analyst)

- **Date:** 2026-10-12
- **Ledger hypothesis ids:** 14, 15, 16 (all 'proposed')
- **Strategy file:** TBD

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
- **Strategy file:** TBD

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
TBD

---

## Idea 2 (H15): Trend-conditioned volatility throttle (vol ignored in uptrends)
- **Ledger hypothesis id:** 15
- **Strategy file:** TBD

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
TBD

---

## Idea 3 (H16): CPPI-style drawdown cushion with trend-gated re-risking
- **Ledger hypothesis id:** 16
- **Strategy file:** TBD

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
TBD
