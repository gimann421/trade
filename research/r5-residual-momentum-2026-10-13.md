# Round 5: residual momentum in the point-in-time S&P 500 (hypothesis 33)

- **Date:** 2026-10-13
- **Ledger hypothesis id:** 33
- **Strategy file:** TBD
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

## Data coverage
TBD

## Results
TBD
