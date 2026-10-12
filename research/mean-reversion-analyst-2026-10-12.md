# Short-term mean reversion in uptrends (SPY, QQQ)

- **Date:** 2026-10-12
- **Ledger hypothesis ids:** 5 (RSI(2) pullback), 6 (three down closes), 7 (low IBS close)
- **Strategy file:** TBD

Prior work checked in `memory/ledger.db`: ids 1-4 are trend/volatility ideas (SMA 50/200 cross,
vol targeting, multi-horizon momentum, Donchian breakout). None is mean reversion and none is
rejected, so nothing here repeats or revisits a ledger idea.

## Common rules (all three ideas)

- **Data:** `data/SPY_1Day.csv`, `data/QQQ_1Day.csv` only; each strategy sees one symbol's bars.
- **Weights:** 0 or 1 only (long or flat; no shorting, per `config/risk_limits.yaml`).
- **Trend filter:** close > 200-day simple moving average of closes, on the signal day. Signals are 0
  until 200 bars exist.
- **Fills/costs:** backtester fills at the signal day's close; 5 bps per unit of turnover, so each
  round trip costs 10 bps.
- **Windows:** IS 2016-01-01..2022-12-31, OOS 2023-01-01..2026-10-09. Signals are computed on the full
  history and then sliced, so OOS starts with a warm 200-day SMA. The IS window loses ~10 months to
  warm-up; this penalises the strategy, which is conservative.
- **Benchmark:** buy-and-hold on the same symbol, same dates, 5 bps.

### Kill threshold (fixed now, identical for ideas 5, 6 and 7)

For each symbol (SPY and QQQ) and each window (IS and OOS), at 5 bps, the idea is killed if **either**:

1. strategy Sharpe (daily returns including flat days, annualised x252) < buy-and-hold Sharpe; **or**
2. net return per day in the market (sum of daily net strategy returns / number of days with
   position > 0) < **2x** buy-and-hold mean daily return.

Condition 2 is fair to a part-time strategy: it asks whether each day of exposure earns clearly more
than an average day of simply holding. Condition 1 stops a strategy that is good per day but too
rarely invested from being called better than holding.

A window with **fewer than 15 entries** is inconclusive and cannot count as a pass.
**Supported only if it passes both windows on both SPY and QQQ** (4 out of 4).

### Do 5 bps costs kill the edge?

A round trip costs 10 bps. Ideas 5 and 6 hold 1-5 days and historically averaged well over 0.3% per
trade on index ETFs, so costs should take a minority of the edge, if the edge still exists. Idea 7
holds about 1 day and trades most often, with a historical average next-day gain of perhaps
0.15-0.3%. Costs could take half of that or more, so idea 7 is the most likely to fail on costs.
Condition 2 is net of costs, so it tests this directly.

---

## Idea 5: RSI(2) oversold pullback in uptrend (ledger id 5)

### Hypothesis
Going long SPY/QQQ at the close when RSI(2) < 10 and close > 200-day SMA, then exiting at the first
close above the 5-day SMA, beats buy-and-hold on Sharpe and earns at least 2x buy-and-hold's daily
return per day in the market after 5 bps costs, in both 2016-2022 and 2023-2026.

Fixed parameters: RSI period 2 (Wilder smoothing), entry RSI < 10, trend SMA 200, exit when close >
SMA(5). Weight 1 from entry close until the exit close, inclusive. No stop and no time limit.

### Why it might work
Sharp 1-3 day selloffs inside a bull market are mostly driven by demand for liquidity, not by news
that changes long-run value. That demand comes from stop-losses, margin calls, vol-target and
risk-parity deleveraging, retail panic and ETF outflows. The buyer is paid for supplying that
liquidity. The other side is forced or impatient sellers. The 200-day filter avoids buying into
bear-market waterfalls (2018 Q4 late stage, 2020 March, 2022).

**Market conditions needed:** a longer-term uptrend (close > SMA200) with short, liquidity-driven
dips that recover within days. The idea fails in regimes where dips keep extending, such as the early
stage of a crash while price is still above the 200-day SMA (Feb 2020).

### How it could fail
The kill threshold above applies. The idea was widely published (Connors, 2008), so the edge may have
been arbitraged down, and the OOS window is the test of that.

### Test plan
SPY and QQQ; IS 2016-01-01..2022-12-31, OOS 2023-01-01..end; 5 bps; benchmark buy-and-hold.

### Results
TBD

---

## Idea 6: Three consecutive down closes in uptrend (ledger id 6)

### Hypothesis
Going long SPY/QQQ at the close of the third consecutive lower close (close_t < close_t-1 <
close_t-2 < close_t-3) while close > 200-day SMA, then exiting at the first higher close or after 5
trading days held, whichever comes first, beats buy-and-hold on Sharpe and earns at least 2x
buy-and-hold's daily return per day in the market after 5 bps costs, in both windows.

Fixed parameters: N = 3 down closes, trend SMA 200, exit at the first close > prior close, or at the
close of the 5th day held. Further down closes while in the trade do not extend the 5-day limit.
Re-entry needs a fresh 3-down-close count.

### Why it might work
Daily returns of index ETFs have shown negative short-horizon autocorrelation since about 2000,
because market makers and arbitrageurs absorb order flow. Streaks of down closes overshoot as sellers
who chase momentum or deleverage pile in. The other side is sellers who extrapolate short streaks.
A pure count rule differs from the RSI(2) trigger: it fires on slow grinds as well as sharp drops,
and its exit is faster (first up close).

**Market conditions needed:** close > SMA200 and choppy, range-bound pullbacks rather than a
persistent slide.

### How it could fail
The kill threshold above applies. A further risk is that losing streaks become longer, so the 5-day
time stop locks in losses.

### Test plan
SPY and QQQ; IS 2016-01-01..2022-12-31, OOS 2023-01-01..end; 5 bps; benchmark buy-and-hold.

### Results
TBD

---

## Idea 7: Low IBS close in uptrend, one-day hold (ledger id 7)

### Hypothesis
Going long SPY/QQQ for the next day when the close is in the bottom 20% of the day's range (IBS =
(close - low) / (high - low) < 0.2, treated as no signal if high == low) and close > 200-day SMA beats
buy-and-hold on Sharpe and earns at least 2x buy-and-hold's daily return per day in the market after
5 bps costs, in both windows.

Fixed parameters: IBS threshold 0.2, trend SMA 200. Weight is 1 on a qualifying day and 0 otherwise,
so the position is held over day t+1 only. Back-to-back qualifying days keep the position with no
added cost.

### Why it might work
A close near the day's low reflects end-of-day liquidity pressure: market-on-close imbalances,
rebalancing of leveraged and inverse ETFs (which sell into weak closes), and intraday stop-outs. Part
of that pressure reverses overnight and the next day. The other side is end-of-day flow that must
trade regardless of price. This trigger uses the day's range (high/low), not only closes, so it is
distinct from ideas 5 and 6.

**Market conditions needed:** close > SMA200 and enough intraday range for IBS to carry meaning.
This is the highest-turnover idea, so it needs a per-trade edge clearly above 10 bps.

### How it could fail
The kill threshold above applies. This idea is the most exposed to the 5 bps cost and to the
optimistic close fill.

### Test plan
SPY and QQQ; IS 2016-01-01..2022-12-31, OOS 2023-01-01..end; 5 bps; benchmark buy-and-hold.

### Results
TBD
