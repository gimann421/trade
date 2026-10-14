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
TBD

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
TBD
