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
- ETF bars for all 20 ETFs used (nine sector SPDRs, SPY, QQQ, IWM, EFA, EEM, VNQ, VTI, BIL, IWB, IWD, IWF) were re-downloaded to 2026-10-12 before the run; none had missing trading days.
- Stocks: the same 719 point-in-time members and bars as H33; at least 99% of members are priced at every rebalance.
- Scan run at commit 8f9ccff (the registration commit); raw output is `backtests/factor_scan_v1/scan_20261013T115856Z.json`.

## Results
**Two of 37 rules pass the bar in both windows: `stock_resmom6_1_decile` and `stock_resmom6_1_quintile`** (6-1 month residual momentum on point-in-time S&P 500 members, top decile and top quintile). They are one signal at two sizes, so this is one finding, not two. The other 35 rules fail.

Windows: IS 2017-02-01..2022-12-30 (71 rebalances), OOS 2023-01-03..2026-10-12 (46 rebalances). Net active is against the family's benchmark after 5 bps costs.

### The two passing rules
| Rule | Window | Net active/yr | IR | Placebo | CAGR vs benchmark | Sharpe vs benchmark | Max drawdown | Beta | Turnover/yr |
|---|---|---|---|---|---|---|---|---|---|
| decile (~50 names) | IS | +4.30% | 0.49 | 1.000 | 15.2% vs 10.3% | 0.78 vs 0.57 | -36.9% | 0.90 | 12.2x |
| decile | OOS | +8.43% | 0.68 | 1.000 | 22.8% vs 13.6% | 1.25 vs 0.98 | -21.9% | 0.92 | 11.3x |
| quintile (~100 names) | IS | +3.50% | 0.51 | 1.000 | 14.4% vs 10.3% | 0.76 vs 0.57 | -36.8% | 0.91 | 9.6x |
| quintile | OOS | +2.74% | 0.31 | 0.984 | 16.5% vs 13.6% | 1.06 vs 0.98 | -20.3% | 0.91 | 9.1x |

Report-only checks:
| Rule | Delayed fill, net active IS / OOS | Spin-off-cleaned, net active IS / OOS (IR) |
|---|---|---|
| decile | +4.28% / +7.80% (IR 0.49 / 0.63) | +4.44% / +7.53% (0.51 / 0.61) |
| quintile | +3.07% / +1.88% (IR 0.45 / 0.21) | +3.67% / +2.48% (0.54 / 0.28) |

Things to know about the winners:
- The decile result survives a one-day-late rebalance and the spin-off clean-up with little change. The quintile's out-of-sample result is marginal: IR 0.31 against the 0.3 bar, and its delayed-fill IR is 0.21, below it.
- Beta to equal-weight members is about 0.9 and the maximum drawdown (-37% in-sample) is about as deep as the benchmark's: this is a return tilt, not a risk reduction. It also turns over about 12x a year (included in the net figures).
- The same signal over 12-1 months is H33, which failed in-sample (+0.86%/yr). The 6-1 version passed both windows. The two versions differ only in lookback (6 vs 12 months) and were judged on the same years, so part of the difference may be luck; the forward paper period is the check.
- Plain 6-1 and 12-1 momentum (no factor stripping) fail in-sample and pass only out-of-sample; the stripping step is what fixed the in-sample years.
- Putting a trend filter on it (`stock_resmom6_1_decile_trend`) removes the whole edge (net active about 0 in both windows) while cutting beta to 0.3-0.6: it becomes a lower-risk fund of similar return to the benchmark, not an excess-return rule.

### Chance and counts
- Rules passing the placebo alone: 4 in-sample, 9 out-of-sample. Rules passing the full bar: 3 in-sample, 6 out-of-sample, 2 in both.
- The two winners are the same signal at two sizes. No other signal passes both windows.
- Hypotheses tested so far: 70. A scan of this size passes a few rules per window by luck alone; the in-sample pass of `etf_region_mom3_k2` that failed out-of-sample is an example of that. Paper trading is the check on the two that passed.

### All rules
**Family A: ETF rotation**

| Rule | IS net active/yr | IS IR | IS placebo | OOS net active/yr | OOS IR | OOS placebo | Bar |
|---|---|---|---|---|---|---|---|
| `etf_sect_mom3_k2` | +3.3% | +0.30 | 0.85 | -3.5% | -0.32 | 0.23 | fails |
| `etf_sect_mom3_k3` | +2.1% | +0.26 | 0.82 | -0.7% | -0.08 | 0.45 | fails |
| `etf_sect_mom6_k2` | +1.4% | +0.13 | 0.64 | -4.8% | -0.45 | 0.14 | fails |
| `etf_sect_mom6_k3` | +0.3% | +0.03 | 0.55 | -6.8% | -0.89 | 0.02 | fails |
| `etf_sect_mom12_1_k2` | +5.1% | +0.45 | 0.91 | +3.4% | +0.34 | 0.78 | fails |
| `etf_sect_mom12_1_k3` | +3.4% | +0.40 | 0.87 | +2.7% | +0.36 | 0.79 | fails |
| `etf_sect_rev1_k2` | -5.9% | -0.53 | 0.06 | -6.8% | -0.65 | 0.09 | fails |
| `etf_sect_rev1_k3` | -4.2% | -0.50 | 0.07 | -2.6% | -0.33 | 0.28 | fails |
| `etf_region_mom3_k1` | +5.0% | +0.46 | 0.95 | -3.3% | -0.31 | 0.30 | fails |
| `etf_region_mom3_k2` | +3.1% | +0.46 | 0.95 | -2.7% | -0.36 | 0.23 | fails |
| `etf_region_mom6_k1` | +3.1% | +0.27 | 0.80 | -0.8% | -0.07 | 0.45 | fails |
| `etf_region_mom6_k2` | +0.1% | +0.01 | 0.57 | -5.4% | -0.72 | 0.03 | fails |
| `etf_region_mom12_1_k1` | +3.2% | +0.28 | 0.80 | +1.6% | +0.15 | 0.64 | fails |
| `etf_region_mom12_1_k2` | +0.6% | +0.09 | 0.64 | +0.6% | +0.08 | 0.58 | fails |
| `etf_region_rev1_k1` | +3.5% | +0.31 | 0.89 | -8.8% | -0.83 | 0.03 | fails |
| `etf_region_rev1_k2` | -2.6% | -0.37 | 0.16 | -7.8% | -1.10 | 0.01 | fails |

**Family B: stock factors**

| Rule | IS net active/yr | IS IR | IS placebo | OOS net active/yr | OOS IR | OOS placebo | Bar |
|---|---|---|---|---|---|---|---|
| `stock_mom12_1_decile` | -0.3% | -0.03 | 0.27 | +10.7% | +0.62 | 1.00 | fails |
| `stock_mom12_1_quintile` | -0.1% | -0.01 | 0.31 | +5.7% | +0.51 | 1.00 | fails |
| `stock_mom6_1_decile` | -0.0% | -0.00 | 0.60 | +7.2% | +0.43 | 1.00 | fails |
| `stock_mom6_1_quintile` | -0.4% | -0.04 | 0.47 | +3.8% | +0.35 | 1.00 | fails |
| `stock_resmom6_1_decile` | +4.3% | +0.49 | 1.00 | +8.4% | +0.68 | 1.00 | **passes** |
| `stock_resmom6_1_quintile` | +3.5% | +0.51 | 1.00 | +2.7% | +0.31 | 0.98 | **passes** |
| `stock_rev1_decile` | -0.2% | -0.02 | 0.79 | -3.7% | -0.31 | 0.04 | fails |
| `stock_rev1_quintile` | +0.1% | +0.01 | 0.90 | -4.2% | -0.49 | 0.00 | fails |
| `stock_lowvol_decile` | -0.4% | -0.03 | 0.41 | -7.3% | -0.62 | 0.00 | fails |
| `stock_lowvol_quintile` | +0.5% | +0.05 | 0.73 | -7.0% | -0.72 | 0.00 | fails |
| `stock_lowbeta_decile` | -1.2% | -0.08 | 0.17 | -5.8% | -0.41 | 0.00 | fails |
| `stock_lowbeta_quintile` | -1.2% | -0.09 | 0.11 | -6.4% | -0.52 | 0.00 | fails |
| `stock_high52_decile` | -2.5% | -0.20 | 0.11 | -5.9% | -0.56 | 0.01 | fails |
| `stock_high52_quintile` | -0.5% | -0.05 | 0.49 | -3.5% | -0.41 | 0.01 | fails |

**Family C: stock factors with a trend filter**

| Rule | IS net active/yr | IS IR | IS placebo | OOS net active/yr | OOS IR | OOS placebo | Bar |
|---|---|---|---|---|---|---|---|
| `stock_mom12_1_decile_trend` | -4.6% | -0.23 | 0.01 | -0.7% | -0.04 | 1.00 | fails |
| `stock_mom6_1_decile_trend` | -3.4% | -0.17 | 0.29 | -2.7% | -0.15 | 0.96 | fails |
| `stock_resmom6_1_decile_trend` | -0.1% | -0.01 | 0.98 | +0.0% | +0.00 | 1.00 | fails |
| `stock_rev1_decile_trend` | -2.7% | -0.14 | 0.62 | -13.2% | -1.03 | 0.00 | fails |
| `stock_lowvol_decile_trend` | -3.5% | -0.18 | 0.20 | -8.3% | -0.64 | 0.18 | fails |
| `stock_lowbeta_decile_trend` | -4.7% | -0.23 | 0.03 | -5.5% | -0.38 | 0.74 | fails |
| `stock_high52_decile_trend` | -4.8% | -0.26 | 0.04 | -7.2% | -0.62 | 0.45 | fails |

Other findings:
- Short-term reversal, low volatility, low beta and nearness to the 52-week high all lost to equal weight out-of-sample (low volatility and low beta by 5.8% to 7.3% a year).
- ETF rotation: 12-1 momentum is positive in both windows in all four universe and size variants (+0.6% to +5.1% in-sample, +0.6% to +3.4% out-of-sample). Only the sector versions come near the bar (+5.1% / +3.4% in-sample, +3.4% / +2.7% out-of-sample for k = 2 / 3), and their placebos (0.78-0.91) are too low.

## Running count
Hypotheses tested so far: 70; two (one signal) supported.
