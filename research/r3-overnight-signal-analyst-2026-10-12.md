# Overnight/intraday return-split signals (round 3): three ideas

- **Date:** 2026-10-12
- **Ledger hypothesis ids:** 26 (overnight-strength tilt), 27 (overnight-component trend filter), 28 (gap-up-faded washout)
- **Strategy file:** TBD

Paper trading only. No returns, backtests or parameter tuning were run; every parameter below is fixed from convention or the cited work.

## Shared definitions

- `ON_t = ln(open_t / close_{t-1})`, `ID_t = ln(close_t / open_t)`. Weights are long-only in [0, 1], computed from bars up to and including day t, held over day t+1 close-to-close (core/backtest.py). Overnight-only holding is not proposed (10 bp round trip vs about 3.4 bp/day).
- Markets: XLK, XLV, XLF, EEM, HYG. Windows: IS 2016-01-01..2022-12-31, OOS 2023-01-01..end. Cost 5 bps per unit turnover. Signals on full history.
- Pass rule (fixed): `symbol_status(cells, min_symbols=4)` == supported AND mean `placebo_percentile` over passing cells >= 0.95 (min_shift=252, n=1000, seed=0). Metric is stated per idea.
- Negative or tiny buy-and-hold (HYG, EEM, sectors can be weak in a window): all thresholds are additive offsets to B&H, never multiples of B&H return. Where B&H Sharpe <= 0 in a window, a cell additionally needs strategy Sharpe >= 0 (losing less than a negative benchmark does not count).
- "Inconclusive" cells block SUPPORTED (a symbol passes only if both windows "supports"); they do not by themselves reject.
- Research basis (snippet-level, not read in full): Lou, Polk and Skouras, "A Tug of War": momentum profits accrue overnight, others intraday (US individual stocks 1993-2013, not ETFs). "Day Destroys the Night, Night Extends the Day": past smoothed overnight market returns negatively forecast later close-to-close returns, mainly via intraday mean reversion (index level; smoothing window not known to me, so 20d is my own convention).

## Open-price data check (counts only, no return statistics)

All five files: 2709 rows, 2016-01-04..2026-10-12, no duplicate dates, no NaN, no calendar gap > 5 days, no zero volume, open never outside [low, high], close never outside [low, high], no open <= 0. Open == close: XLK 34, XLV 24, XLF 55, EEM 55, HYG 100 days. Open == prior close: XLK 59, XLV 58, XLF 81, EEM 35, HYG 159 (5.9% of HYG days). Oddities to keep in mind:
- Opens are from a single feed. For HYG a flat open against the prior close on 6% of days suggests coarse/quote-based opens (and ON for HYG is tiny relative to tick size), so ON-based signals on HYG are the least trustworthy.
- Prices are dividend-adjusted; I could not verify without return stats that open and close are adjusted by the identical factor on ex-dividend dates. Any mismatch would put a one-day artefact into ON (largest for HYG, monthly dividends). Implementation must compute ON from the same adjusted series as given and the verdict must be read with this caveat.
- Last row is 2026-10-12 (today); if that bar is partial, the final OOS day is unreliable (it has no t+1 return so is unscored, but it enters rolling windows).

## How these differ from the ledger (H9 and others) and from the round-1/2 lesson

H9 exited to 0 on clusters of large gap-DOWNS on SPY/QQQ (stress regime). H2/H8/H10/H15/H20 are vol/range de-risking, H1/H3/H4/H14/H16 close-to-close trend, H5-7/H18/H19 close-based short-term reversal, H11-13 calendar, H23-25 multi-asset allocation. None uses strength of overnight returns (idea 1), the overnight component alone as a trend sign (idea 2), or an intraday-only z-score conditioned on a positive gap (idea 3).
Lesson (de-risking liquid ETFs cut drawdown but lost too much return): idea 1 is deliberately bounded (floor 0.5, so give-up is at most half the drift in de-risked days) and is judged on Sharpe plus a capped CAGR give-up, not on drawdown; if the forecasting effect is not present in these ETFs it will simply look like a half-position drag and fail. Idea 2 does NOT escape the lesson by construction; I rate it likely to repeat H3 and include a close-to-close control to find out whether the split adds anything. Idea 3 is an add-exposure rule with low market exposure, so the lesson is not the relevant failure mode; its risk is costs and sample size.

## Idea 1: Overnight-strength tilt (ledger id 26)

### Hypothesis
Holding each ETF at weight 1, but 0.5 after its 20-day sum of overnight returns reaches the top quintile of its own trailing year, raises Sharpe by at least 0.05 over buy-and-hold at a CAGR give-up of at most 2 points, after 5 bps.

### Exact rule
- `S_t = sum_{k=0..19} ON_{t-k}`. `P_t` = fraction of the 252 values `S_{t-251..t}` that are <= `S_t` (includes itself).
- Warm-up: weight 1 until `P_t` is defined (first valid row index 270 zero-based = 271st row; `ON_0` is NaN).
- State machine: weight 0.5 once `P_t >= 0.80`; return to 1 when `P_t < 0.60` (hysteresis); otherwise keep prior weight.
- Parameters: 20d = one month (my convention; the index paper's exact smoothing unknown); 252d = one year; 0.80 = top quintile convention; 0.60 = midpoint of median and entry. None tuned.
- Costs: each switch trades 0.5 unit = 2.5 bps.

### Why it might work
Past strong overnight runs forecast weaker later close-to-close returns through intraday reversal (index-level report). Who is on the other side: overnight buyers (futures/Asian and European sessions, momentum traders) pushing opens up, against intraday liquidity providers who fade them; the effect would be a slow-moving limit of arbitrage across sessions, not a risk premium. Why not already arbitraged: I do not know that it is not; the evidence is index-level and old, so this is a genuine out-of-sample test on sector/EM/credit ETFs.

### Market conditions required
Monthly-horizon mean reversion in the overnight component. It fails in persistent bull trends where XLK/XLF overnight sums stay in the top quintile for months (the strategy then sits at 0.5 through the rally), and for HYG where ON is tiny and noisy. EEM is the best candidate because its overnight window embeds the Asian session.

### How it could fail (decided now)
Cell (symbol, window) verdict:
- supports: `Sharpe_s >= Sharpe_bh + 0.05` AND `CAGR_s >= CAGR_bh - 0.02` (and Sharpe_s >= 0 if Sharpe_bh <= 0);
- contradicts: otherwise, provided de-risk episodes (weight 1 -> 0.5 transitions in the window's position series) >= 8 IS / >= 4 OOS;
- inconclusive: fewer episodes than that.
Veto: if ANY of the 10 cells has `Sharpe_s < Sharpe_bh - 0.20` or `CAGR_s < CAGR_bh - 0.04`, status cannot be SUPPORTED even if 4 symbols pass. Placebo metric: `sharpe` (return_per_exposure_day is degenerate as exposure is ~100%). Rejected if <4 symbols can still pass.

### Test plan
5 symbols x 2 windows, 5 bps, benchmark = buy-and-hold per cell. Strategy file TBD. Report per cell: Sharpe, CAGR, number of episodes, share of days at 0.5.

### Results
TBD

## Idea 2: Overnight-component trend filter (ledger id 27)

### Hypothesis
Holding each ETF only while its 126-day cumulative overnight log return is positive cuts maximum drawdown by 5 points and matches buy-and-hold Sharpe after 5 bps.

### Exact rule
- `T_t = sum_{k=0..125} ON_{t-k}`. Weight 1 if `T_t > 0`, else 0. Warm-up: weight 1 for the first 126 rows (T first defined at index 126).
- Parameters: 126d = six months, within the standard time-series-momentum range and already one rung of H3 (so no new tunable); sign test, no threshold.
- Control (diagnostic only, not in verdict): identical rule with `ID+ON` (close-to-close) 126d sum. If the control passes a cell the overnight rule fails, or both pass identically, report that the split adds nothing.

### Why it might work
Lou et al. find momentum-type profits accrue overnight and that the intraday component is mean-reverting noise, so a trend sign from overnight alone may whipsaw less than close-to-close. Other side: holders who keep full exposure through trend breaks and intraday traders whose reversals contaminate close-to-close trend. Candid prior: low. It is a slow binary trend rule and H1/H3/H4 on SPY/QQQ were rejected; I expect drawdown reduction with return give-up unless the overnight sign is cleaner.

### Market conditions required
Trends that persist for months with turning points visible in overnight returns (2022 XLK/XLF drawdown, 2018Q4-style slides, EEM's multi-year chop). Fails in V-shaped crashes/recoveries (Feb-Apr 2020, Apr 2025) where a 126-day window exits late and re-enters late.

### How it could fail (decided now)
Cell supports iff `core.verdicts.drawdown_rule(r, dd_margin=0.05, sharpe_mult=1.0)` returns no fails AND `Sharpe_s >= 0` AND `CAGR_s >= CAGR_bh - 0.05`. Contradicts if not, provided the window has >= 4 position changes (entries + exits); otherwise inconclusive (a six-month filter may trade <= 2 times in OOS; I accept that this can leave the idea untestable). Veto: any cell with `Sharpe_s < Sharpe_bh - 0.30` blocks SUPPORTED. Placebo metric: `sharpe`.

### Test plan
5 symbols x 2 windows, 5 bps; B&H per cell; control run for comparison.

### Results
TBD

## Idea 3: Gap-up-faded intraday washout (ledger id 28)

### Hypothesis
After a day that gaps up overnight and then sells off by more than 2 standard deviations of recent intraday moves, the next three days earn at least 10 bps per day more than the average buy-and-hold day, net of 5 bps costs, in at least 55% of events.

### Exact rule
- `z_t = ID_t / std(ID_{t-60..t-1})` (sample std, 60 values, excludes day t).
- Trigger at close of day t: `z_t <= -2.0` AND `ON_t > 0`. Then weight 1 for exactly 3 trading days (signal days t, t+1, t+2 so the position is held over returns of t+1, t+2, t+3); triggers during a hold are ignored (no extension); otherwise weight 0. Weight 0 in the first 61 rows.
- Parameters: 60d = one quarter std; -2.0 = standard "extreme" cut-off; ON > 0 defines the gap-up-then-fade pattern (no magnitude); 3d = about half a week, short enough that the 10 bp round trip is spread over 3 days. Not tuned.

### Why it might work
Tug-of-war framing: overnight buying faded by intraday selling that is large relative to normal intraday ranges looks like a transient liquidity/flow event (end of intraday selling pressure), after which prices recover. Other side: intraday sellers who hand back the move over the next sessions. Overlap with H7 (low IBS close) is real: a -2z intraday fade usually closes near its low, so H7's rejection lowers my prior.

### Market conditions required
Intraday over-reaction that recovers within 3 days; needs enough events (about 3-6 per year per symbol if intraday z is roughly normal and half have ON > 0). Fails in persistent selloffs (2022 XLK, 2020 March) where the fade continues. HYG has too small and coarse ON/ID to give a meaningful z; expect few or noisy triggers there.

### How it could fail (decided now)
Cell supports iff `return_per_exposure_day >= B&H mean_daily_return + 0.0010` (additive, so negative B&H is handled) AND the share of events whose net 3-day return is > 0 is >= 55%. Contradicts if not, provided the window has >= 15 events IS / >= 6 events OOS; otherwise inconclusive (OOS is only about 3.8 years so many cells may be inconclusive and the idea untestable on some symbols; I accept that). Veto: any cell with `return_per_exposure_day < 0` blocks SUPPORTED. Placebo metric: `return_per_exposure_day`.

### Test plan
5 symbols x 2 windows, 5 bps (10 bps per event), B&H per cell; report events, hit rate, mean net event return.

### Results
TBD

## Honest limits of this sample

Ten years, one bull-dominated regime, 5 ETFs that are highly correlated (XLK/XLV/XLF vs each other and EEM), so "4 of 5 symbols" is closer to 2-3 independent looks. Window IS contains 2018Q4, 2020 and 2022; OOS contains one long rally and the 2025 spring selloff. Three ideas at 10 cells each raise the chance of a lucky pass; the 0.95 placebo bar partly offsets it. A SUPPORTED result would be weak evidence; a REJECTED result is also weak for idea 2 and 3 where cells may be inconclusive.
