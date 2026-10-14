# Round 8: short-horizon stock rules on daily bars (hypotheses 71-89)

- **Date:** 2026-10-14
- **Ledger hypothesis ids:** 71-89, one per rule (title "Short-horizon v1: <rule id>")
- **Strategy file:** `strategies/short_horizon_v1.py`; scoring in `research/round8_short_horizon.py`
- **Why:** a monthly rule makes about 12 decisions a year, so judging it takes years. A rule that decides every 1-10 trading days makes hundreds, so a good or bad rule shows itself in weeks to months of data. This round tests whether any short-horizon rule on S&P 500 stocks survives realistic costs, and measures how many weeks of data each needs to be told apart from luck.
- **What was known when this was written:** the results of H1-H70; that the short-horizon index and ETF rules failed in 2016-2026 (H5 and H6 passed on 2000-2015); the Alpaca-versus-Yahoo cross-check (`research/free-data-sources-2026-10-14.md`). A 60-stock sample showed Alpaca's stock bars agree with Yahoo's to a median of 0.3 bps a day outside March 2020, and that 37 of 66 disagreements over one point fall in March 2020. No return of any rule below had been computed.
- **Part A (this memo, now):** price-only rules. **Part B** (earnings-date events from SEC filings) gets its own section, written and committed before its data is pulled.

Multiple-testing count: these are hypotheses 71-89, so eighty-nine will have been tested. Two (one signal) are supported and in the forward record; the rest are rejected or, for H1, unresolved.

## Prior
Low. Short-term reversal is old and well known (weekly and monthly reversal; liquidity provision); published work I recall (not re-checked here) finds it concentrated in small, illiquid stocks and much weaker or gone among large caps since the 2000s, with a visible collapse of quant contrarian profits in August 2007. The overnight-versus-intraday result (Lou, Polk and Skouras) is from the earlier research summary and also not re-checked. The reason to run it anyway is speed of evidence.

## Rules (exact)
Universe and benchmark as in round 6: point-in-time S&P 500 members priced on the decision date (same membership file and Alpaca bars as H33); benchmark = equal weight of all priced members, rebalanced at month-end, same costs.

- **Decisions:** every `h`-th scheduled session from the close of 2016-12-30, for h in {1, 2, 5, 10}. Targets are traded at the decision close and held to the next decision close; weights drift in between.
- **Selection:** the top decile (round of 10% of ranked names) or, where marked `_q`, the top quintile, by signal, equal weight.
- **Signals** (higher is better; a name is ranked only if every return in the window exists):
  - `rev1`: minus the 1-day return. `rev5`: minus the 5-day return. `rev10`: minus the 10-day return.
  - `on5`: the sum of the last 5 overnight log returns (previous close to open), i.e. buy persistent overnight strength.
  - `id5`: minus the sum of the last 5 intraday log returns (open to close), i.e. buy persistent intraday weakness.
- **The 19 rules:** `rev1_h1`, `rev1_h2`, `rev1_h5`, `rev5_h2`, `rev5_h5`, `rev5_h10`, `rev10_h5`, `rev10_h10`, `on5_h2`, `on5_h5`, `on5_h10`, `id5_h2`, `id5_h5`, `id5_h10`, and the quintile versions `rev1_h5_q`, `rev5_h5_q`, `rev10_h5_q`, `on5_h5_q`, `id5_h5_q`.
- **Costs:** 5 bps per unit of turnover against drifted holdings (a full turnover costs 10 bps), the primary setting; 10 bps as a stress.
- **Windows:** in-sample holding days from 2017-01-03 to 2022-12-30, out-of-sample from 2023-01-03 to the end of data. A decision belongs to the window containing its holding period's first day.

## Bar (the existing one, plus execution checks)
A rule is **supported** only if all of these hold:
1. In each window: annualized net active return (mean daily strategy minus benchmark net return x 252) >= +2.0%; information ratio (mean daily active / its sd x sqrt(252)) >= 0.3; selection placebo >= 0.95 (as many names as the rule holds drawn at random from the ranked names at each decision, equal weight; statistic = mean gross active return per holding period; 1000 draws, seed 0). At least 48 decisions in-sample and 36 out-of-sample (every rule meets this).
2. **Delayed fill:** with every target traded one session late (decided at close t, traded at close t+1), net active return is above 0 in both windows.
3. **Cost stress:** at 10 bps per unit, net active return is above 0 in both windows.

A rule that passes 1 but fails 2 or 3 is rejected and labelled "execution-sensitive" in the evidence row. A rule that fails 1 is rejected. The extra checks exist because a short hold turns a small fill or cost error into most of the edge, as it did for the month-end Treasury rule (H31).

## Data handling fixed in advance
- **March 2020.** Alpaca's closes for 2020-03-09 to 2020-03-19 disagreed with Yahoo's by over a point on several stocks each day, and the error reverses the next day. A reversal rule would read that as a profit. All strategy and benchmark returns on the 10 sessions 2020-03-09 to 2020-03-20 are dropped from every statistic, and decisions whose holding period touches those sessions are left out of the placebo.
- **Spin-offs.** As in H33, single-day moves below -50% or above +100% are not removed in the primary run.

## Reported for every rule (no bar attached)
- Gross active return, annual turnover, and the break-even cost (the cost per unit of turnover at which net active return reaches zero).
- **Weeks of data needed:** from the information ratio over the whole scored period, years to a t-statistic of 2 = (2 / IR)^2, shown in weeks (only for a positive IR). This is the answer to "how long does it take to tell a good short-horizon rule from a bad one".
- Beta to the benchmark.

## How it could fail
Large-cap reversal and overnight effects are small per trade, so the cost line is the likely killer: a rule that turns the whole book over every 5 days pays about 5% a year at 5 bps, and a daily one about 25%. Expect most of the 19 to fail the cost or delayed-fill checks even if their gross edge is positive.

## Part A: data and results
Data: the 719 point-in-time members' Alpaca bars (open and close), 2016-12-30 to 2026-10-12, 10 sessions in March 2020 excluded. The run took 6.5 minutes at commit fb33a4d.

**All 19 rules are rejected. None is supported.**

| Rule | Gross active IS / OOS | Net active IS / OOS | IR IS / OOS | Placebo IS / OOS | Turnover/yr | Break-even cost (bps per unit) IS / OOS | Fills a session late, IS / OOS | At 10 bps, IS / OOS |
|---|---|---|---|---|---|---|---|---|
| `rev1_h1` | +5.2% / +14.0% | -16.4% / -7.8% | -1.25 / -0.60 | 1.00 / 1.00 | 434x | 1.2 / 3.2 | -20.0% / -12.4% | -38.1% / -29.6% |
| `rev1_h2` (passes the bar OOS, fails execution checks) | +2.0% / +16.3% | -8.9% / +5.5% | -0.70 / +0.41 | 0.90 / 1.00 | 218x | 0.9 / 7.5 | -4.6% / -3.5% | -19.8% / -5.4% |
| `rev1_h5` | -0.6% / +10.5% | -4.9% / +6.1% | -0.36 / +0.45 | 0.39 / 1.00 | 87x | -0.7 / 12.0 | -2.4% / +6.0% | -9.2% / +1.7% |
| `rev5_h2` (passes the bar OOS, fails execution checks) | +8.6% / +11.6% | +1.5% / +4.4% | +0.11 / +0.32 | 1.00 / 1.00 | 142x | 6.1 / 8.1 | +1.0% / -0.7% | -5.6% / -2.8% |
| `rev5_h5` | +4.9% / +2.8% | +0.6% / -1.6% | +0.04 / -0.12 | 1.00 / 0.88 | 88x | 5.7 / 3.2 | +4.1% / -0.4% | -3.8% / -6.0% |
| `rev5_h10` | -0.7% / +4.2% | -2.9% / +2.0% | -0.23 / +0.18 | 0.30 / 0.98 | 44x | -1.7 / 9.6 | -1.9% / -0.4% | -5.1% / -0.2% |
| `rev10_h5` | +0.6% / +4.4% | -2.6% / +1.1% | -0.19 / +0.09 | 0.78 / 0.97 | 64x | 0.9 / 6.8 | -0.0% / -2.4% | -5.8% / -2.1% |
| `rev10_h10` | +0.0% / +3.2% | -2.1% / +1.0% | -0.16 / +0.09 | 0.55 / 0.95 | 44x | 0.1 / 7.2 | -0.9% / -1.8% | -4.3% / -1.2% |
| `on5_h2` | -0.9% / -0.6% | -7.5% / -7.3% | -0.65 / -0.59 | 0.14 / 0.32 | 134x | -0.6 / -0.5 | -9.2% / -7.7% | -14.2% / -14.0% |
| `on5_h5` | +2.2% / -0.6% | -2.1% / -4.9% | -0.19 / -0.40 | 0.68 / 0.33 | 86x | 2.5 / -0.8 | -5.3% / -5.5% | -6.4% / -9.1% |
| `on5_h10` | -1.4% / +1.6% | -3.6% / -0.5% | -0.36 / -0.05 | 0.04 / 0.77 | 44x | -3.3 / 3.8 | -5.6% / +1.8% | -5.7% / -2.6% |
| `id5_h2` (passes the bar OOS, fails execution checks) | +9.9% / +11.1% | +2.7% / +3.9% | +0.21 / +0.32 | 1.00 / 1.00 | 144x | 6.9 / 7.7 | +3.3% / -4.2% | -4.4% / -3.3% |
| `id5_h5` | +4.4% / +0.3% | +0.1% / -4.1% | +0.00 / -0.33 | 1.00 / 0.53 | 87x | 5.1 / 0.3 | +0.6% / -4.3% | -4.3% / -8.4% |
| `id5_h10` | -2.7% / +1.5% | -4.9% / -0.7% | -0.41 / -0.06 | 0.03 / 0.71 | 44x | -6.3 / 3.4 | -5.1% / -4.1% | -7.1% / -2.8% |
| `rev1_h5_q` | +0.3% / +5.7% | -3.6% / +1.8% | -0.36 / +0.19 | 0.73 / 1.00 | 78x | 0.4 / 7.3 | -1.9% / +2.6% | -7.5% / -2.1% |
| `rev5_h5_q` | +4.3% / +2.0% | +0.4% / -2.0% | +0.04 / -0.22 | 1.00 / 0.89 | 79x | 5.5 / 2.5 | +2.4% / -1.5% | -3.6% / -6.0% |
| `rev10_h5_q` | +0.5% / +3.7% | -2.2% / +0.9% | -0.22 / +0.10 | 0.85 / 0.99 | 56x | 1.0 / 6.6 | +1.5% / -2.9% | -5.0% / -1.9% |
| `on5_h5_q` | +0.1% / +1.1% | -3.8% / -2.7% | -0.44 / -0.31 | 0.12 / 0.76 | 78x | 0.1 / 1.5 | -5.2% / -3.8% | -7.6% / -6.5% |
| `id5_h5_q` | +3.9% / +0.0% | -0.0% / -3.9% | -0.00 / -0.47 | 1.00 / 0.46 | 79x | 5.0 / 0.0 | +0.6% / -3.5% | -3.9% / -7.8% |

What this says:
- **There is a gross edge, and costs take it all.** 13 of 19 rules earned a positive gross active return in both windows, and the one-to-two-day reversal rules earned a lot (`rev1_h1` +5% in-sample and +14% out-of-sample; `rev1_h2` +16% out-of-sample; `rev5_h2` and `id5_h2` +9% to +12%). But a rule that turns the book over every day or two trades 140 to 430 times a year, and the **break-even cost is only 1 to 8 bps per unit of turnover**. At 5 bps most rules net out negative; at 10 bps every rule-window is negative except one (`rev1_h5` out-of-sample, +1.7%).
- **The edge is the part you cannot capture.** Fills one session late, which is a more honest model of acting on a close you have just seen, turn most of the gross edge negative (for example `rev1_h1` goes from +5% gross in-sample to -20% net, and the three one-to-two-day rules below go negative out-of-sample). That is the signature of compensation for providing liquidity at the close, available to someone who can trade at the closing price at near-zero cost, not to a retail account.
- **Four rules pass the return bar out-of-sample; none passes it in-sample.** `rev1_h2`, `rev5_h2` and `id5_h2` fail the execution checks (negative when filled a session late and at 10 bps). `rev1_h5` (buy the 10% biggest one-day losers, hold five sessions) passes everything out-of-sample (net +6.1%, information ratio 0.45, placebo 1.00, +6.0% when filled late, +1.7% at 10 bps) but loses 4.9% a year in-sample with a placebo of 0.39, so it is rejected. Its out-of-sample gross edge (+10.5%) against -0.6% in-sample looks like a change of regime around 2023, the same shape as plain momentum earlier; it is a lead to watch on new data, not a result.
- **Overnight strength (`on5`) has no net edge in either window** and almost no gross edge (at most +2.2% in-sample).

### How many weeks of data it takes
The measure is weeks until a t-statistic of 2 if the measured information ratio were the true one, (2 / IR)^2 years. It is only defined for a positive IR. Net of costs, **17 of the 19 rules have a negative information ratio over 2017-2026, so there is nothing to detect**; the two positive ones, `id5_h2` (IR 0.25) and `rev5_h2` (IR 0.19), would need about 3,300 and 5,600 weeks (63 and 107 years). For comparison, the 6-1 month residual momentum rule (IR about 0.5 to 0.7) needs roughly 600 weeks (12 years), and a rule with a net IR of 1.0 would need about 208 weeks (4 years); a net IR of 2.0 would need 52 weeks. **More decisions per year only speeds up evidence if the edge per decision survives costs.** Here it does not, so shortening the horizon bought no speed.


## Part B: earnings-announcement drift from SEC filings (hypotheses 90-93)
Written and committed before any filing was downloaded and before any return of these rules was computed. Part A's results were already known when this was written: all 19 rules were rejected, with gross edges of 2-16% a year eaten by costs, and the break-even cost per unit of turnover was only 1-8 bps.

### Idea
Stocks whose price jumps on an earnings release keep drifting in the same direction for weeks (post-earnings-announcement drift; Chan, Jegadeesh and Lakonishok used the announcement-day return as the signal). The holding periods are 5 to 60 sessions, so costs are small relative to the hold. Prior: low to medium: the drift is well documented but is reported to have shrunk, especially in large, heavily followed stocks.

### Universe and data
- Events are 8-K filings with Item 2.02 ("Results of Operations") from the SEC's `data.sec.gov` submissions service, one request or two per company.
- **Only today's S&P 500 constituents have a usable company number** (the constituent file at fja05680/sp500 carries one for 503 of them); delisted members have none. To keep that survivorship out of the comparison, **both the rule and its benchmark are restricted to point-in-time members that are also current constituents**, and the benchmark is equal weight of that same set, rebalanced monthly. The result therefore says nothing about survivorship-free performance; it asks whether ranking events beats not ranking them within one fixed set of stocks.
- Prices: the same Alpaca daily bars; the same 2020-03-09 to 2020-03-20 exclusion as Part A.

### Event timing
- The acceptance time of the filing is converted to New York time. Before 09:30 the reaction session R is that day's session (or the next one if that date is not a session); at 09:30 or later R is the next session after the acceptance date. (Releases during market hours are therefore measured from the next session, which understates their reaction.)
- Reaction return AR = the stock's close-to-close return on R minus the equal-weight return of the restricted set on R.
- Two filings by the same company on the same R count once.

### Rules (exact)
- An event **qualifies** at the close of R if AR is at or above the q-th percentile of the ARs of all events with reaction sessions in the 252 sessions before R (strictly earlier), with at least 100 such events; the company must be a point-in-time member on R and priced.
- A qualifying event is held from the close of R through the close of R + h (h sessions of holding). Weights are equal across all names with an active qualifying event; the portfolio trades only on days when that set changes, and holds BIL when it is empty.
- **The four rules:** `pead_q80_h5`, `pead_q80_h20`, `pead_q80_h60` (q = 80), and `pead_q90_h20` (q = 90).
- Costs 5 bps per unit of turnover; stress 10 bps; delayed fill = every target one session later.

### Bar
As in Part A. Windows: in-sample decisions from 2017-01-03 to 2022-12-30, out-of-sample from 2023-01-03. In each window: net active >= +2.0%/yr, information ratio >= 0.3, **event placebo** >= 0.95, and at least 200 qualifying events in-sample and 100 out-of-sample (else inconclusive). Event placebo: the mean h-session abnormal return after R (stock return minus the equal-weight return of the set over the same sessions) of the qualifying events in the window, compared with the same mean for random draws, of the same number of events, from all events with sufficient history in that window (1000 draws, seed 0). Delayed-fill and 10 bps net active must also be above 0 in both windows.

### Reported
Events found, qualifying events per window, average AR of qualifiers, gross active return, turnover, break-even cost, weeks of data to a t-statistic of 2 (as in Part A).

### Limits
Current-constituent filter (above); 8-K filings for results are not a complete earnings calendar (companies that release inside another form are missed); Item 2.02 is also used for guidance updates; the event count per window is the binding constraint on how much the placebo can say.

### Part B data and results
Data: 21,268 earnings releases (SEC 8-K Item 2.02) by current S&P 500 constituents from 2016 on, 18,083 of them on dates when the company was a point-in-time member; the universe and the benchmark are restricted to those names. Timing check: the mean absolute stock return is 3.4% on the mapped reaction session against 1.2% to 1.9% on the two sessions either side (150 companies, 2018-2019), so the release dates map to the right sessions, with some releases landing one session early. The run took 19 seconds at commit c501545.

**All 4 rules are rejected. None is supported.**

| Rule | Qualifying events IS / OOS | Mean reaction AR of qualifiers IS / OOS | Mean h-session abnormal return, qualifiers vs all events (IS) | Net active IS / OOS | IR IS / OOS | Event placebo IS / OOS | Gross active IS / OOS | Late fill IS / OOS | At 10 bps IS / OOS |
|---|---|---|---|---|---|---|---|---|---|
| `pead_q80_h5` | 1772 / 1394 | +5.8% / +7.7% | -0.12% vs -0.08% | -13.1% / -2.5% | -0.66 / -0.11 | 0.30 / 0.43 | -6.4% / +4.3% | -2.4% / -10.6% | -19.7% / -9.4% |
| `pead_q80_h20` | 1772 / 1391 | +5.8% / +7.7% | +0.07% vs -0.16% | -0.9% / -3.5% | -0.09 / -0.35 | 0.94 / 0.72 | +1.9% / -0.8% | -1.0% / -7.2% | -3.6% / -6.3% |
| `pead_q80_h60` | 1772 / 1304 | +5.8% / +7.6% | -0.13% vs -0.52% | +0.6% / +0.6% | +0.16 / +0.15 | 0.95 / 0.91 | +1.3% / +1.3% | +1.0% / +0.9% | -0.1% / -0.0% |
| `pead_q90_h20` | 828 / 686 | +7.9% / +10.8% | -0.06% vs -0.16% | -5.8% / +2.7% | -0.44 / +0.17 | 0.70 / 0.97 | -3.1% / +5.6% | -7.2% / -2.7% | -8.5% / -0.1% |

What this says:
- **A little drift, far too small to trade.** Qualifying events had large reactions (average abnormal return +5.8% in-sample, +7.7% out-of-sample). Over 5 sessions they do no better than the average event (-0.12% against -0.08% in-sample); over 20 to 60 sessions they beat it by 0.1 to 0.5 points per event in both windows (for example -0.13% against -0.52% over 60 sessions in-sample, -0.74% against -1.18% out-of-sample). The event placebos run from 0.30 to 0.97; only `pead_q80_h60` in-sample (0.95) and `pead_q90_h20` out-of-sample (0.97) reach 0.95.
- **The best rule, `pead_q80_h60`, is flat.** Net active +0.6% a year in both windows (information ratio 0.15 to 0.16), gross +1.3%, trading 15 times a year with break-even costs near 9 to 10 bps. It is nowhere near the 2% bar.
- The short holds lose most of their return to turnover (`pead_q80_h5` trades 134 times a year in-sample).
- **Limit:** the stocks are today's constituents and the benchmark is the same set, so this answers whether ranking events helps within that set, not whether the drift exists across all stocks (small stocks and delisted names are where the literature finds it).

## Round summary
Hypotheses tested so far: 93; none new supported. Short-horizon stock rules have a gross edge that does not survive realistic costs or a one-session fill delay, and earnings-announcement drift is absent among current large caps.

