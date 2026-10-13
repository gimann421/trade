# Round 5: residual momentum in the point-in-time S&P 500 (hypothesis 33)

- **Date:** 2026-10-13
- **Ledger hypothesis id:** 33
- **Strategy file:** `strategies/residual_momentum_v1.py`; scoring in `research/round5_verdicts.py`, summary in `backtests/round5_summary.json`; data plumbing in `core/universe.py`
- **Source:** idea 3 of "New Trading Ideas — Round 4 Research" (Claude Docs, https://claude.ai/artifact/UWRKnia66kJGerwuqnmk6T), run on its own after round 4 (H31, H32, both rejected). The rule and kill thresholds below are the doc's; reading choices where it is silent are listed separately. All of it is fixed before any strategy code is written or any return is computed. Membership and price files were downloaded before this memo was written; only their coverage (which tickers have bars) was looked at, no returns.

Multiple-testing count: this is hypothesis 33. Thirty-two have been tested before it; none supported.

## Hypothesis
Firm-specific news diffuses slowly, so S&P 500 stocks with persistently positive factor-stripped (residual) returns over the past year, skipping the last month, keep outperforming; holding the top decile equal-weight beats an equal-weight portfolio of all members by at least 2% a year net, with an information ratio of at least 0.3, in both windows.

## Rule (exact)
- **Universe:** S&P 500 members on each formation date, from point-in-time membership (fja05680/sp500, "S&P 500 Historical Components & Changes (Updated).csv", sha256 3632670…0d54, rows to 2026-08-18). Members on a date are the latest row dated on or before it.
- **Factors** (daily returns of ETFs already used): MKT = VTI − BIL, SMB = IWM − IWB, HML = IWD − IWF.
- **Formation**, at each scheduled NYSE month-end close t: for each member with at least 231 valid daily returns among the 232 trading days t−252 to t−21, regress its daily return on a constant and the three factors over the valid days of that window. Residual return = stock return − betas × factors (the constant is kept in it). Score = mean residual return ÷ its standard deviation, same window.
- **Holding:** the top decile by score (round(0.1 × ranked names), about 50) equal-weight, bought at the close of t and held to the next month-end close; weights drift in between.
- **Benchmark:** equal weight of all point-in-time members with a close on t, rebalanced at each month-end close, same costs.
- **Costs:** 5 bps per unit of turnover on the drifted weights, for both. Cash earns 0%.
- **Warm-up:** no positions in either line before the first month-end at which any member has 231 valid returns (expected 2017-01-31, since bars start 2016-01-04).
- **Exits:** a holding whose bars end mid-month (delisting, merger) is held as cash at its last close until the next rebalance; the same applies in the benchmark.

## Why it might work
Investors underreact to firm-specific news and sell winners too early. Ranking on residual returns avoids loading on whichever factor just rallied, which is what makes plain momentum crash. The edge is slow and still carries market and crowding risk, which limits arbitrage.

## Evidence (as reported in the doc; all long-short and gross of costs)
- Blitz, Huij & Martens (2011): risk-adjusted profits about twice those of total-return momentum; annualized volatility 12.5% vs 22.7% (CXO summary). https://www.econbiz.de/Record/residual-momentum-blitz-david/10009194616
- Huij & Lansdorp (2017): robust across global universes and after publication; US 1986-2008 13.1% a year at 10.3% volatility vs 16.1% at 21.6% for conventional momentum; the 2009-2015 edge is "mostly modest". https://repub.eur.nl/pub/100801
- No post-2015 US large-cap long-only test found.

## How it could fail (kill rule, per window; benchmark as above)
Supports only if, in each window, all hold:
- annualized net active return (mean daily strategy minus benchmark net return × 252) >= +2.0%;
- information ratio (mean daily active ÷ its standard deviation × sqrt(252)) >= 0.3;
- placebo percentile >= 0.95 (definition below);
- at least 48 rebalances in-sample and 36 out-of-sample.
One universe, so supported only if both windows pass; fewer rebalances than the minimum makes a window inconclusive.

Prior: low-medium (the doc's own). The long-only top decile keeps market beta, the 1-year daily window departs from the published 36-month method, and survivorship plumbing is easy to get wrong.

## Reading choices (where the doc is silent)
- **Windows.** In-sample 2016-01-01..2022-12-31 and out-of-sample 2023-01-01..end of data, as always; days before the first holding day are left out of both lines' statistics (both are flat then, so including them would only dilute the numbers). A rebalance belongs to the window that contains its holding month (the decision at the 2022-12-30 close is out-of-sample), so rebalance counts, the placebo and the daily statistics cover the same days. (Changed from "decision date" in the first commit of this memo, before any code or return existed.)
- **Residual.** With a constant in the regression, residuals fitted and scored on the same window average exactly zero, so the doc's score would be empty. The residual return therefore keeps the constant (stock return minus factor betas × factor returns): the score is the stock's factor-adjusted mean return over its residual volatility. This keeps the doc's intent (rank on stock-specific return, not factor exposure).
- **Placebo** (the doc says only "95th percentile"; a circular shift does not fit a monthly stock-selection rule): at each rebalance, draw as many names as the strategy holds, uniformly from the same ranked names, equal-weight; the statistic is the mean monthly gross active return (the basket's month return minus the benchmark's) over the window's rebalances; 1000 draws, seed 0. Gross, because random baskets turn over about 90% a month against the strategy's 30-40%, so charging costs would tilt the null against the random baskets; costs are judged by the net active rule.
- **Membership after 2026-08-18:** the last row is used for later month-ends (one or two months; stated, not corrected).
- **Tickers.** Each ticker is downloaded with Alpaca's `asof` set to the last membership row listing it, so a renamed company (FB to META) keeps one continuous history. A ticker that named two different member companies inside the window would get only the later one; none is known.
- **Missing data.** Members with no Alpaca bars cannot be ranked or held, and drop out of the benchmark too. The number is reported below; if it is large, results are biased upward and the verdict says so.

## Reported, not scored
- Delayed fill (every rebalance one trading day late). The round-4 delayed-fill rule targeted holds of five days or fewer; a monthly hold is reported only.
- Plain 12-1 total-return momentum (same universe, same decile, same mechanics), to see what the residual step adds.
- Turnover, the strategy's beta to the benchmark, and data coverage.
- Spin-off check. Alpaca's adjusted bars cover splits and dividends but not spin-offs, so a parent's spin-off date shows as a false one-day loss (seen before any returns were computed: UTX/RTX -71% on 2020-04-03, ARNC -89% on 2020-04-01, TGNA -78% on 2017-06-01, APTV -72% on 2017-12-05). It hits strategy and benchmark alike when both hold the name. A second simulation (signals unchanged) sets every single-day stock move below -50% or above +100% to zero; it is reported, not scored, and it also removes real crashes such as SIVB.

## Data coverage
- All 719 tickers that were members at some month-end from December 2016 on returned Alpaca bars, delisted ones included (SIVB, FRC, TWTR and others).
- Only 50 member-months lacked a close on the month-end, across 9 tickers (WYND 17, APTV 11, BHGE 7, AABA 6, IR 5, and one each for FTI, INFO, CTXS, TWTR). Those are mostly name changes around corporate events. At least 99.0% of members were priced at every rebalance (99.9% on average).
- About 501 names were ranked per rebalance (minimum 495), giving 50 picks each time.
- The survivorship bias the doc warned about is therefore small here. Unadjusted spin-offs are the larger data issue; see the spin-off check below.

## Results
**Rejected.** Out-of-sample passes; in-sample fails all three tests; both windows were required. The first rebalance was 2017-01-31.

| Window | Rebalances | Net active / yr | Information ratio | Placebo | CAGR, strategy vs EW members | Sharpe | Max drawdown | Cell |
|---|---|---|---|---|---|---|---|---|
| IS 2017-02-01..2022-12-30 | 71 | +0.86% | 0.09 | 0.755 | 11.1% vs 10.3% | 0.60 vs 0.57 | -38.0% vs -39.8% | fails (all three) |
| OOS 2023-01-03..2026-10-12 | 46 | +10.14% | 0.79 | 1.000 | 25.0% vs 13.6% | 1.36 vs 0.98 | -15.1% vs -17.7% | passes |

Reported, not scored:

| Window | Delayed fill, net active (IR) | Plain 12-1 momentum, net active (IR) | Spin-off check, net active (IR) |
|---|---|---|---|
| IS | +0.62% (0.06) | -0.34% (-0.03) | +1.07% (0.11) |
| OOS | +8.91% (0.69) | +10.71% (0.62) | +10.10% (0.79) |

- Other figures:
  - Turnover: 8.8x a year in-sample and 7.9x out-of-sample, two-sided. That is about 35% a month one-way, in line with the doc's 30-40%.
  - Benchmark turnover: about 0.75x.
  - Beta to the benchmark: 0.92 in-sample, 0.86 out-of-sample.
  - Tracking error: 9.7% in-sample, 12.9% out-of-sample.
- Benchmark check: equal-weight members compounded 10.3% a year over 2017-2022, close to RSP's figure for those years from memory, so the membership and price plumbing looks right.

What this says:
- **Out-of-sample:**
  - 2023 to now is a very strong period for this rule: +10% a year over equal weight, information ratio 0.79, and better than every one of 1000 random 50-name baskets.
  - It survives a one-day-late rebalance and the spin-off check.
  - Plain 12-1 momentum earned as much over the benchmark (+10.7%). The window rewarded momentum in general (the 2023-2025 large-cap trend), not the residual step in particular.
  - Where the residual step did help was risk: 17.5% volatility against 23.0% for plain momentum, and -15% maximum drawdown against -24%, as the papers report.
- **In-sample (2017-2022):**
  - The edge is under 1% a year, information ratio 0.09, placebo 0.755.
  - That period includes the November 2020 factor reversal the doc named as the main way this fails.
- **Overall:** the pattern is the reverse of earlier rounds, a weak in-sample and a strong out-of-sample. Passing out-of-sample after failing in-sample is not support under the pre-set rule, and the out-of-sample run coincides with an unusually strong momentum regime.
- **Possible follow-up:** test residual momentum as a lower-risk replacement for plain momentum. That would need its own hypothesis and a fresh holdout; the forward paper period is the only unseen data left.

## Running count
Hypotheses tested so far: 33; none supported.
