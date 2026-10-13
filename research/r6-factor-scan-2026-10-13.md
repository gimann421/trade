# Round 6: a scan of 37 rotation and factor rules (hypotheses 34-70)

- **Date:** 2026-10-13
- **Ledger hypothesis ids:** 34-70, one per rule (title "Scan v1: <rule id>")
- **Strategy file:** `strategies/factor_scan_v1.py`; scoring in `research/round6_scan.py`
- **What this is:** a search. Thirty-seven rules from three families are scored once each against the bar already used for earlier rounds, and any rule that passes both windows is marked supported and goes to paper trading. The rule list below is fixed before any return is computed; it cannot grow after results are seen.
- **What was known when this was written:** the author had seen the results of all thirty-three earlier hypotheses on 2016-2026, including that momentum-type rules did well from 2023. The families below were chosen with that knowledge. The decision (the user's) is that choosing ideas from the data is fine and the bar is unchanged.

Multiple-testing count: these are hypotheses 34-70, so seventy are tested after this round. Thirty-three before it; none supported.

## Common mechanics (all 37 rules)
- Decisions at scheduled NYSE month-end closes from 2017-01-31 (the first month-end with 252 trading days of history). Every rule starts on that date, so all rules share the same windows. Targets are traded at the decision close and held to the next decision close; weights drift in between.
- Equal weight across picks. Costs: 5 bps per unit of turnover against the drifted holdings, for strategy and benchmark. Cash earns 0% except where BIL is held.
- Windows: in-sample from 2017-02-01 to 2022-12-30 (71 rebalances), out-of-sample 2023-01-03 to the end of data (about 46). A rebalance belongs to the window containing its holding month.
- Data: Alpaca daily bars, split- and dividend-adjusted. Spin-offs are not adjusted (seen in H33); the primary run uses the raw series. Passing rules get a report-only second run with single-day moves below -50% or above +100% set to zero.
- Return window notation: "days t-L..t-s" means the daily returns of those trading days (L-s+1 of them). A name is ranked only if it has at least L-s of them, so a stock with a short history or two or more missing returns is not ranked.

## The 37 rules

### Family A: ETF rotation (16 rules)
Hold the top k ETFs by signal, equal weight. Benchmark: equal weight of the whole universe, monthly.
- Universes: SECT = XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY (k = 2 or 3); REGION = SPY, QQQ, IWM, EFA, EEM, VNQ (k = 1 or 2).
- Signals: `mom3` (return, days t-63..t), `mom6` (t-126..t), `mom12_1` (t-252..t-21), `rev1` (minus the return of days t-20..t, i.e. buy last month's losers).
- Rule ids: `etf_{sect|region}_{signal}_k{k}`.

### Family B: stock factors in the point-in-time S&P 500 (14 rules)
Members from the same membership file as H33 (sha256 3632670...0d54), priced on the decision date. Hold the top decile (round of 10% of ranked names) or quintile (20%). Benchmark: equal weight of all priced members, monthly.
- `mom12_1`: return of days t-252..t-21. `mom6_1`: days t-126..t-21.
- `resmom6_1`: the H33 residual score (daily returns on a constant and MKT = VTI-BIL, SMB = IWM-IWB, HML = IWD-IWF; score = mean residual / sd, constant kept in the residual) over days t-126..t-21, at least 105 valid returns. (The 12-month version is H33 and not repeated.)
- `rev1`: minus the return of days t-20..t.
- `lowvol`: minus the standard deviation of daily returns over days t-251..t, at least 231 valid.
- `lowbeta`: minus the slope of daily returns on VTI's daily returns over days t-251..t, at least 231 valid pairs.
- `high52`: close divided by the highest close of days t-251..t, at least 231 valid.
- Rule ids: `stock_{signal}_{decile|quintile}`.

### Family C: stock factors with a trend filter (7 rules)
The decile portfolio of each of the seven Family B signals, but 100% BIL at any decision close where VTI is not above its 200-day average (needs 200 closes); the benchmark stays the unfiltered equal-weight members. Rule ids: `stock_{signal}_decile_trend`. These must therefore beat equal-weight members by +2% a year with the filter's cash months included.

## How a rule is judged (the existing bar, unchanged)
In each window, all of:
- annualized net active return against the benchmark (mean daily strategy minus benchmark net return x 252) >= +2.0%;
- information ratio (mean daily active / its sd x sqrt(252)) >= 0.3;
- selection placebo >= 0.95: at each rebalance draw as many names as the rule holds, uniformly from the same ranked names, equal weight; statistic = mean monthly gross active return over the window's rebalances; 1000 draws, seed 0. (In a month where a trend filter is off, every draw equals the actual, so those months cancel.)
- at least 48 rebalances in-sample and 36 out-of-sample (else inconclusive).

A rule is supported if it passes both windows and rejected if either window fails; the ledger status is set to match. Report-only for every rule: delayed fill (all targets one trading day late), beta to the benchmark, turnover. Report-only for passing rules: the spin-off-cleaned run, and whether the rule's neighbours (other size, other k) also pass.

## Reading choices
- Rules share one start date so windows match; this drops about 6 months of the 2016 history for the shorter signals.
- Ties broken by ticker. A ranked-name count under k, or an empty universe, holds what is available.
- Stocks whose bars end mid-month are held as cash at their last close (their price is carried forward) until the next rebalance.
- Chance passes: at a 95% placebo bar about one rule in twenty passes the placebo in one window by luck. The two-window requirement cuts this a lot but not to zero (and rules sharing a signal are not independent). The write-up will state how many rules passed each window separately.

## Data
TBD

## Results
TBD
