# Volatility-based exposure rules for SPY/QQQ (hypotheses 8-10)

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 8, 9, 10
- **Strategy file:** TBD

Author: volatility-analyst. Scope: volatility-based exposure rules on daily bars only
(`data/SPY_1Day.csv`, `data/QQQ_1Day.csv`, 2016-01-04..2026-10-09). `generate_signals(bars)` sees
one symbol's OHLCV only. Weights are restricted to {0, 1}, so there is no shorting (`allow_short: false`).

## Ledger check (before proposing)

I read the `hypotheses` and `evidence` tables:

| id | title | status |
|----|-------|--------|
| 1 | SMA 50/200 crossover trend filter | testing (SPY contradicts, QQQ inconclusive) |
| 2 | Volatility-targeted exposure (15% target, 20-day realized vol) | proposed |
| 3 | Multi-horizon time-series momentum ladder | proposed |
| 4 | Donchian breakout with 21-day-low exit | proposed |
| 5 | RSI(2) oversold pullback in uptrend | proposed |
| 6 | Three consecutive down closes in uptrend | proposed |
| 7 | Low IBS close in uptrend, one-day hold | proposed |

None of them has status `rejected`, so nothing is being revived. The ideas below are built to differ
materially from all seven:

- **vs. hypothesis 2 (vol targeting):** H2 sets a continuous weight from the absolute level of 20-day
  close-to-close vol and changes it every day. All three ideas here are binary (0/1) and change rarely,
  at about 2-6 round trips a year, so costs are about 10 bps per round trip instead of daily
  turnover. Each one also uses a different input: (8) the *change* in vol relative to the symbol's own
  100-day baseline, (9) overnight gaps only, and (10) single-day intraday true-range shocks with a fixed
  time stop.
- **vs. hypotheses 1, 3, 4 (trend):** none of these rules uses price level, moving averages or trailing returns.
- **vs. hypotheses 5-7 (mean reversion):** those rules buy weakness inside uptrends, and H7 uses where the
  close sits in the day's range. Idea 10 does the opposite: it treats a large-range down day as a reason
  to step aside, whatever the trend.

To check that the rules fire often enough to be tested, I counted their signal episodes on the cached
data. I computed no returns and ran no parameter variations. Number of exits (1 to 0):

| rule | SPY IS | SPY OOS | QQQ IS | QQQ OOS |
|------|--------|---------|--------|---------|
| 8 vol-ratio | 17 | 8 | 21 | 6 |
| 9 gap cluster | 32 | 17 | 33 | 16 |
| 10 range shock | 38 | 16 | 35 | 15 |

## Common test plan and kill rule (applies to 8, 9, 10)

- Symbols: SPY and QQQ, each tested separately. **An idea must pass on BOTH symbols.**
- Windows: in-sample 2016-01-01..2022-12-31; out-of-sample 2023-01-01..2026-10-09. Signals are computed
  on the full history and then sliced, so warmup does not eat into the OOS window. Each window is judged
  on its own, and **an idea must pass both windows.**
- Costs: 5 bps per unit of turnover, filled at the signal day's close (`core/backtest.py`).
- Benchmark: buy-and-hold on the same symbol and the same dates, also at 5 bps.
- **Kill (numerical, fixed now):** for each symbol and window, the idea is killed if
  (a) its Sharpe is below buy-and-hold Sharpe, OR
  (b) its max drawdown is not at least 5 percentage points shallower than buy-and-hold's
  (e.g. buy-and-hold -20.0% requires the strategy to be at -15.0% or better).
  If a window has fewer than 2 flat episodes, the result is inconclusive and the idea is not supported.
  The idea is supported only if it passes all 4 cells (SPY/QQQ x IS/OOS).
- Parameters below are final. There will be no tuning sweeps; any change means a new hypothesis.

---

## Idea 8: Vol-ratio spike switch with hysteresis (ledger id 8)

### Hypothesis
Hold SPY/QQQ at weight 1, and go to weight 0 at the close when 10-day realized vol (std of daily log
close-to-close returns) exceeds **1.5x** the 100-day realized vol. Go back to 1 only when the ratio falls
below **1.0**. Use weight 1 during the 100-day warmup. The claim is that this beats buy-and-hold on
Sharpe and cuts max drawdown by at least 5 points after 5 bps costs.

### Why it might work
Volatility clusters, and a sudden jump in vol relative to its recent norm tends to come with drawdowns
(the leverage effect, deleveraging cascades, and vol-target/risk-parity funds selling with a lag). The rule
is keyed to the *change* in vol, not its level. That means it catches spikes that start in a calm regime
(Feb 2018, Aug 2024) even when absolute vol is modest, and it does not leave QQQ permanently
under-invested because its vol is naturally higher. Both are weaknesses of H2's fixed 15% target. The
hysteresis band (out above 1.5, in below 1.0) means it waits until vol has normalised before re-entering,
which should avoid whipsaw.
**Other side:** dip buyers and constant-allocation holders who stay fully exposed into a vol shock.

### Market conditions it needs
Drawdowns that arrive with a fast rise in short-term vol from a calm base (shock-style selloffs:
2018, 2020, 2025). It will not help in slow grinding bear markets where vol rises gradually and the
100-day baseline keeps up (parts of 2022). It also needs vol spikes to be followed on average by poor or
volatile returns rather than V-shaped rebounds.

### How it could fail
It fails if it hits the common kill rule above on SPY or QQQ in either window. The most likely way: it exits
near the bottom of a V-shaped recovery and re-enters late, giving up the rebound. That would leave Sharpe
below buy-and-hold without a 5-point drawdown improvement.

### Results
TBD

---

## Idea 9: Overnight gap-down cluster exit (ledger id 9)

### Hypothesis
Hold SPY/QQQ at weight 0 whenever **at least 2 of the last 10 sessions** (including today) had a
**down gap**, and at weight 1 otherwise. A down gap is open_t / close_{t-1} - 1 < -2 x (mean absolute
overnight gap over the 60 sessions ending at t-1). The claim is that this beats buy-and-hold on Sharpe
and cuts max drawdown by at least 5 points after 5 bps costs.

### Why it might work
Overnight gaps carry information that arrives while the US cash market is closed, such as macro and
policy news and Asian/European selloffs. A cluster of unusually large down gaps marks a stress regime in
which risk keeps arriving off-hours and holders cannot react until the open. The gap threshold scales to
each symbol's own recent gap size, so it adapts to QQQ vs SPY. This uses only the overnight part of
returns, which close-to-close vol (H2) blends with intraday moves and which H5-H7 ignore.
**Other side:** intraday dip buyers who absorb gap-downs during the session, and holders who stay fully
exposed overnight through a stress regime.

### Market conditions it needs
Stress regimes driven by overnight or global news flow (e.g. Feb-Mar 2020, 2022 rate shocks, April 2025
tariff gaps), where gap-down clusters lead or coincide with the bulk of the drawdown. It fails in
markets where gaps are routinely bought and filled intraday.

### How it could fail
It fails if it hits the common kill rule above on SPY or QQQ in either window. The most likely way:
gap-down clusters mark short-term capitulation, so the rule is flat right before strong rebounds.

### Results
TBD

---

## Idea 10: Down-day range-shock 10-day timeout (ledger id 10)

### Hypothesis
Hold SPY/QQQ at weight 0 from the close of any **shock day** through the next **10 trading days**, and
at weight 1 otherwise. Each new shock restarts the 10-day count. A shock day is one where close_t <
close_{t-1} and the true range (max(high, prev close) - min(low, prev close)) exceeds **2.0x** the
average true range of the prior 20 days, excluding today. The claim is that this beats buy-and-hold on
Sharpe and cuts max drawdown by at least 5 points after 5 bps costs.

### Why it might work
A down day with an outsized high-low range points to a liquidity event, such as forced selling, margin
calls or dealer short-gamma hedging. The aftermath of such days has fat-tailed follow-through for one to
two weeks before vol mean-reverts, and stepping aside avoids those tails. The rule is event-driven with a
fixed time stop, unlike H2's continuous estimate or idea 8's regime ratio, and it uses intraday true
range rather than close-to-close returns. It is the opposite bet to H5-H7.
**Other side:** short-gamma dealers and dip buyers who supply liquidity into the shock. If dip buying
reliably wins (as H5-H7 bet), this rule misses the rebounds and fails. In that case the two families
give each other informative evidence.

### Market conditions it needs
Selloffs in which the first large-range down day is followed by more large moves within two weeks
(2018 Q4, 2020, 2022, 2025). It needs shock days to be relatively rare in calm uptrends. The count
check above shows the rule flat about 23-33% of days, which is the main cost risk to the Sharpe test.

### How it could fail
It fails if it hits the common kill rule above on SPY or QQQ in either window. Watch for a high flat fraction
in bull years giving up too much return to clear the Sharpe bar.

### Results
TBD
