# Round 2 volatility-regime ideas (IWM, TLT, GLD, XLE, EFA)

- **Date:** 2026-10-12
- **Analyst:** volatility-regime-analyst (round 2)
- **Ledger hypothesis ids:** 20, 21, 22
- **Strategy file:** TBD

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
TBD

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
TBD

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
TBD
