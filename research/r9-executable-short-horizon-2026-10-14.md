# Round 9: short-horizon stock rules that can be traded at the close, with fewer trades (hypotheses 94-102)

- **Date:** 2026-10-14
- **Ledger hypothesis ids:** 94-102, one per rule (title "Short-horizon v2: <rule id>")
- **Strategy file:** `strategies/short_horizon_v2.py`; scoring in `research/round9_executable.py`; intraday snapshots from `core/intraday.py`
- **Why:** round 8 found a real gross edge in 1-2 day reversal (5% to 16% a year over the equal-weight members) that costs and a one-session fill delay take away. Two things in that round were never separated from the edge itself: (1) the delay check assumes the rule cannot act on the close it just saw, but a market-on-close order accepts instructions until about 15:50 New York time, so a rule can read the 15:45 price and be filled at the official close; (2) the rules trade the whole book every 1-2 sessions, which a no-trade band can cut sharply. This round tests whether the edge survives when both are modelled honestly.
- **What was known when this was written:** round 8 in full (`research/r8-short-horizon-2026-10-14.md`): all 19 plus 4 rules rejected; `rev5_h2` and `id5_h2` had net active of +1.5% / +4.4% and +2.7% / +3.9% in-sample / out-of-sample at 5 bps with break-even costs of 6 to 8 bps per unit of turnover; `rev1_h5` passed everything out-of-sample but lost 4.9% a year in-sample. No return of any rule below has been computed, and the only 15:45 prices downloaded were AAPL's, to check the file format and that they agree with the daily closes (median gap 0.16%).

Multiple-testing count: these are hypotheses 94-102, so 102 will have been tested; two (one signal) are supported and in the forward record.

## Prior
Low to medium. Reversal that is paid for providing liquidity at the close is the likely source of the edge, so a rule that is filled at the close with a signal read 15 minutes before it should keep most of it, while the realised cost of competing for closing-auction liquidity is not in a flat 5 bps. Band rules are a standard turnover cut and usually give up part of the gross edge. The best guess is that the band versions of `rev5_h2` and `id5_h2` are the only ones with a chance; `rev1` rules lost money in-sample at every setting in round 8 and should fail again.

## Timing model ("snapshot fill")
Universe, benchmark, decisions (every h-th session from the close of 2016-12-30), costs and windows are as in round 8. What changes is the signal on the decision day t:
- The decision-day price is the **15:45 price** (the close of the 15:30-15:45 bar, split- and dividend-adjusted like the daily files). All earlier days use official closes and opens.
- The target is traded at the **official close of t** (the daily bar close, a market-on-close fill), and held to the next decision close. No later information is used; the snapshot is read at least 15 minutes before the fill.
- `rev1` = minus (15:45 price of t / close of t-1 - 1); `rev5` = minus (15:45 price of t / close of t-5 - 1); `id5` = minus the sum of the last 5 intraday log returns, the last one measured open of t to the 15:45 price.
- A name is ranked only if its snapshot exists on t and every other input exists.

## Rules (exact)
Nine rules, all snapshot-timed, all h = 2 except where marked; selection is the top decile of ranked names, equal weight.
- **Controls (the round-8 rules re-timed):** `rev1_h2_s`, `rev5_h2_s`, `id5_h2_s`, `rev1_h5_s` (h = 5).
- **Band:** `rev1_h2_band_s`, `rev5_h2_band_s`, `id5_h2_band_s`. A held name stays while its signal rank is within the top 30% of ranked names at the decision; names outside it are sold; open slots are filled from the best-ranked names not already held until the book holds as many names as the plain decile would (10% of ranked). A name that is held but not ranked at a decision (no snapshot) is sold.
- **Low volume:** `rev1_h2_lv_s`, `rev5_h2_lv_s`. Reversal is meant to be liquidity-driven, and volume-backed moves tend to continue, so the rule ranks only names whose volume over the signal window is at or below normal: volume ratio = (mean volume to 15:45 over the window's days, i.e. 1 day for `rev1`, 5 for `rev5`) / (mean volume to 15:45 over the 60 sessions before the window); ranked only if ratio <= 1.0. The decile is 10% of the names that pass that filter, so the book is about 5% of members.

## Bar
A rule is **supported** only if all hold:
1. In each window (in-sample holding days 2017-01-03 to 2022-12-30, out-of-sample 2023-01-03 to the end of data): annualized net active return >= +2.0%; information ratio >= 0.3; selection placebo >= 0.95 (as many names as the rule holds, drawn at random from the ranked names at each decision, 1000 draws, seed 0, gross active return per holding period; for low-volume rules the ranked names are those passing the volume filter). At least 250 decisions in-sample and 150 out-of-sample for h = 2 (48 and 36 for h = 5).
2. **Cost stress:** at 10 bps per unit of turnover, net active return is above 0 in both windows.
3. **Snapshot noise:** with the signal built from the 15:30 price (the close of the 15:15-15:30 bar) instead of the 15:45 price, net active return at 5 bps is above 0 in both windows. This checks that the result does not depend on seeing the last 15 minutes.

A rule that passes 1 but fails 2 or 3 is rejected and labelled "execution-sensitive". The one-session delayed fill of round 8 is still reported but no longer gates, because the snapshot fill replaces it as the execution model.

## Reported for every rule (no bar attached)
Gross active return, annual turnover, break-even cost, the round-8 close-timed net active return of the same rule (same-day close signal, same-day close fill, which cannot be traded), delayed-fill net active, weeks of data to a t-statistic of 2 as in round 8, and beta to the benchmark.

## Universe change made before any run (2026-10-14)
The 15-minute history for all 719 members is about 115 million bars and downloads at roughly 9,000 bars a second, which is over three hours. The round therefore uses **a fixed random sample of 300 of the 719 member tickers** (`core.intraday.sample_tickers`, numpy `default_rng(0)`), about 210 of them members on any date. Universe, benchmark (equal weight of the sampled members priced on the date, rebalanced at month-end, same costs) and placebo all use the sample, and a decile is about 20 names. Because the sample changes what the rules hold, the "close-timed" column (same rule, same sample, signal from the official close) is the like-for-like comparison for the effect of the snapshot; the round-8 full-universe numbers are context only. This edit was made before any return of any rule was computed.

## Data handling fixed in advance
- Intraday bars: Alpaca 15-minute bars, adjustment ALL, 2016-12-01 to the last completed session, for the 300 sampled members. Per session only three numbers are kept: the close of the 15:15 bar (the "15:30 price"), the close of the 15:30 bar (the "15:45 price"), and total volume in bars starting from 09:30 up to 15:30 inclusive.
- Check before scoring: the 15:45 price must be within 5% of the same day's official close for at least 99.9% of name-sessions; names-days outside that are dropped from the signal, not repaired. The number dropped is reported.
- March 2020: returns on 2020-03-09 to 2020-03-20 are dropped from every statistic, as in round 8; decisions whose holding period touches those sessions are left out of the placebo.
- Spin-offs: as in round 8, not removed.

## How it could fail
The 15:45 signal may lose the part of the reversal that happens in the last 15 minutes, and that may be most of it. Band rules may cut turnover less than hoped because daily returns reshuffle ranks. Flat 5 bps does not price closing-auction competition, so a pass here is still not a statement that real fills would match. In-sample 2017-2022 had almost no gross reversal edge in `rev1` rules, so out-of-sample strength alone cannot pass a rule. Stocks are only available from 2016, so no older-era check exists for stock rules.

## What a pass would and would not mean
A pass in both windows is evidence for a forward shadow record, as in round 8, not for orders. Passing the bar says nothing about whether a retail broker's market-on-close orders would fill at the official close at 5 bps.

## Results
(to be filled after the run)
