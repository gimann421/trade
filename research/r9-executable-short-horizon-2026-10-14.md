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
Data: 296 of the 300 sampled tickers had snapshots (4 missing at Alpaca); 99.97% of 15:45 prices were within 5% of the official close (197 of 652,000 name-sessions dropped), 99.95% for 15:30, so the agreement check passed. Run at commit 71a8f20 plus the results file `backtests/short_horizon_v2/`. Net active is per year, 5 bps, against the equal-weight sampled members.

**One rule is supported: `rev5_h2_band_s`. The other eight are rejected.**

| Rule | Net active IS / OOS | IR IS / OOS | Placebo IS / OOS | Gross IS / OOS | Turnover/yr | 10 bps IS / OOS | 15:30 signal IS / OOS | Close-timed IS / OOS |
|---|---|---|---|---|---|---|---|---|
| `rev1_h2_s` | -6.3% / +0.8% | -0.43 / +0.05 | 0.93 / 1.00 | +4.5% / +11.6% | 218x | -17.2% / -10.1% | -8.4% / +4.3% | -8.5% / +4.0% |
| `rev5_h2_s` | +2.5% / +8.7% | +0.17 / +0.57 | 1.00 / 1.00 | +9.7% / +16.0% | 144x | -4.6% / +1.4% | +1.7% / +10.4% | +0.5% / +6.1% |
| `id5_h2_s` | +2.8% / +4.1% | +0.19 / +0.29 | 1.00 / 1.00 | +10.1% / +11.4% | 147x | -4.5% / -3.2% | +1.8% / +5.7% | +1.3% / +4.4% |
| `rev1_h5_s` | -5.8% / +10.3% | -0.38 / +0.71 | 0.34 / 1.00 | -1.6% / +14.7% | 86x | -10.1% / +5.9% | -6.8% / +10.2% | -4.2% / +10.0% |
| `rev1_h2_band_s` | -3.2% / +5.2% | -0.23 / +0.35 | 0.97 / 1.00 | +5.3% / +13.6% | 169x | -11.6% / -3.1% | -5.5% / +8.1% | -5.0% / +6.6% |
| **`rev5_h2_band_s`** | **+6.7% / +6.6%** | **+0.43 / +0.45** | **1.00 / 1.00** | +11.4% / +11.3% | 94x | **+2.0% / +1.9%** | **+5.0% / +6.3%** | +5.3% / +7.1% |
| `id5_h2_band_s` | +8.3% / +3.9% | +0.57 / +0.29 | 1.00 / 0.99 | +12.9% / +8.5% | 94x | +3.6% / -0.6% | +5.7% / +5.1% | +5.5% / +3.0% |
| `rev1_h2_lv_s` | -7.6% / -3.4% | -0.51 / -0.21 | 0.79 / 0.93 | +3.6% / +8.0% | 225x | -18.8% / -14.8% | -8.1% / -3.4% | -10.3% / -1.6% |
| `rev5_h2_lv_s` | +0.9% / +10.4% | +0.06 / +0.63 | 0.99 / 1.00 | +9.7% / +19.3% | 176x | -7.8% / +1.5% | +2.2% / +7.5% | +0.1% / +10.6% |

What this says:
- **The 15:45 snapshot costs almost nothing.** Reading the price 15 minutes early gives about the same net active as the impossible close-timed signal (for example `rev5_h2_s` IS +2.5% against +0.5%, OOS +8.7% against +6.1%). Round 8's "edge you cannot capture" reading was mostly the delay model, not the signal: with a market-on-close fill the 2-day reversal rules keep their gross edge. Whether real fills at the close would cost 5 bps is the open question, not the signal timing.
- **The band is what clears the cost line.** It cuts `rev5_h2` turnover from 144x to 94x a year and lifts net active in-sample from +2.5% to +6.7%. `rev5_h2_band_s` passes every part of the bar in both windows, including 10 bps (+2.0% / +1.9%, only just) and the 15:30-signal check. `id5_h2_band_s` has the better in-sample result but fails the 10 bps check out-of-sample (-0.6%) and IR is 0.29 there.
- **`rev1` rules still lose in-sample at every setting** (net -3% to -8%), as expected; the low-volume filter did not rescue them and made `rev5` worse in-sample (+0.9%).
- Out-of-sample (2023+) is stronger than in-sample for every reversal rule except the band ones on `id5`, so part of the edge is a regime that may fade; `rev5_h2_band_s` is steady across the two windows (+6.7% / +6.6%), which is the reason it is more believable than the others.

### Post-hoc check on stocks the round never used
`research/round9_holdout.py` runs the close-timed versions on the other 419 member tickers (no snapshots exist for them, so it cannot be traded and is report-only, not a ledger test). `rev5_h2_band`: net +4.6% IS / +4.7% OOS, IR 0.34 / 0.35, turnover 90x, 10 bps +0.1% / +0.1%; the plain `rev5_h2` there: +1.0% / +6.6%. So the band effect (turnover down by a third, in-sample edge up by about 3.5 points) shows up on unseen stocks, with a smaller margin: at 10 bps it only breaks even.

### Limits and caveats
- One of nine rules passing is not strong evidence on its own: 102 hypotheses have now been tested and the nine are highly correlated. The band version of `rev5_h2` was an expected candidate (named in the prior before any run), which helps, but the band width of 30% and the decile were chosen after seeing round 8.
- The 10 bps margin is thin (+2.0% / +1.9%) and the unseen-stock check breaks even at 10 bps: the rule lives between 5 and 10 bps of true cost.
- A 300-stock sample, flat 5 bps, no closing-auction imbalance cost, no borrow or tax; fills at the official close are assumed available for a ~20-name book that trades about half its names every two days.
- Delayed fill (a session late) is still negative out-of-sample for the close-timed holdout (-1.9%), so the edge depends on acting before the close, not after seeing it.
- Stocks are only available from 2016; there is no older-era check.

### Recommendation
`rev5_h2_band_s` meets the bar the project set, so under the existing rules it earns a forward shadow record (no orders), which is what measures the real 15:45-to-close behaviour. Adding it to the paper tracker is a separate change that this round did not make.

### Forward record (added 2026-10-14, on the user's go-ahead)
`rev5_h2_band_s` is tracked as `stock_rev5_h2_band` (shadow only, allocation 0, never places orders) by `core/snapshot_tracker.py`, run from `core.paper_runner run`. Decisions fall on every second session from 2026-10-15, on the **full** point-in-time S&P 500 (not the 300-name sample the backtest used), with picks and the 15:45 prices written once to `paper/stock_rev5_h2_band/decisions/`. The shadow NAV fills at the official close with 5 bps on turnover against an equal-weight benchmark of the members priced on both days of each interval. Because the runner executes after the close, a decision file shows what the rule would have picked from the 15:45 price but cannot prove it was committed before the 15:50 order cut-off; the first-month check is that the runner runs every trading day without gaps. No stopping rules are set (the project's tracking rules are still a draft).
