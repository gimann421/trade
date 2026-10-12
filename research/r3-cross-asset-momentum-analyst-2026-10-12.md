# Cross-asset momentum: dual momentum, canary-protected and breadth-protected allocation (round 3)

- **Date:** 2026-10-12
- **Ledger hypothesis ids:** 23 (dual momentum), 24 (canary-protected / DAA-style), 25 (breadth-protected / PAA-style); all status `proposed`
- **Strategy file:** TBD

No backtest, return computation or parameter tuning was done for this memo; only row counts were checked (about 2709 daily bars per symbol, 2016-01-04 to 2026-10-12). Every parameter below is fixed now from published work or reasoning.

## Shared context (applies to all three ideas)

**How this differs from H1-H22.** Those are single-asset rules (SMA/Donchian/vol/calendar/mean-reversion on SPY, QQQ, IWM, TLT, GLD, XLE, EFA and the like). Each idea here allocates across a basket by cross-sectional ranking and a graded cash fraction at month-end. None re-uses an H1-22 signal, lookback or universe logic; H3 (multi-horizon time-series momentum ladder on SPY/QQQ) is the nearest relative, and ideas 1-3 differ by ranking assets against each other, choosing among them and parking cash in BIL.

**Literature, as reported, with caveats.**
- PAA (Keller & Keuning): about 10.4% CAGR vs about 8.2% for 60/40 over 1993-2015, out of sample relative to the design. The comparison was against 60/40, not an equal-weight basket of the same assets; trading costs were probably understated early in the sample; results depend on which assets are in the universe.
- DAA (Keller & Keuning): beat its predecessor on CAGR in most universes but with deeper drawdowns.
- Antonacci dual momentum: results are the author's own long-history backtests; ETF histories are far shorter. I have not verified his figures and quote none.
- Plain sector momentum has had lower Sharpe than SPY out of sample. This bears on the alternate sector universes of ideas 2 and 3.

**Mechanism and the other side.** Momentum is thought to arise from slow information diffusion, underreaction, herding and slow-moving institutional capital; absolute (time-series) momentum adds the fact that drawdowns in risk assets tend to be persistent and correlated across risk assets. Who loses: fixed-allocation holders and rebalancers who sell winners and buy losers, benchmark-constrained managers who cannot go to cash, and dip-buyers who keep adding through a persistent decline. The risks that pay for it: whipsaw after V-shaped reversals and tracking error vs buy-and-hold. Edges like this are widely published, so a smaller post-publication edge is the expectation.

**Regimes needed, and what 2016-2026 can show.** The ideas need (a) persistent multi-month trends in at least some asset classes and (b) drawdowns that develop over weeks to months, so a month-end signal exits before most of the loss. They fail in fast V-shaped crashes (the lagging signal exits late and re-enters late) and in choppy markets. The sample has one crash (Feb-Mar 2020), one bear year (2022, stocks and bonds both fell, so cash/BIL is the only hedge), a Q4 2018 drawdown, and a 2025 sharp reversal. That is roughly three or four independent drawdown events: power is low, a pass is weak evidence, and the sample cannot say anything about 2008-style slow bears, 1970s inflation or a long bond bull. The 252-day warm-up means the IS window starts effectively in early 2017; the strategy sits 100% in BIL (earning the BIL rate) while the benchmarks are invested. This is a known handicap, accounted for by the 3-point CAGR tolerance below.

**OOS contamination.** The 2023-onward window has been seen in earlier rounds for single-asset rules on SPY, EFA, TLT, GLD and others. It has not been used for these rules, but the market path is known to us and to the author, who also knows published results, so the OOS window is not a clean holdout. All parameters are fixed here and must not change after the first run. Three ideas x two universes x two windows is a dozen comparisons; the all-cells-must-pass rule is the guard against luck, but ideas 2 and 3 are highly correlated (same data, similar signals) and should not be counted as independent confirmation of each other.

**Common mechanics for the strategy file (to be written later).**
- Decision at the last trading day's close of each month (`core.portfolio.month_ends`; the final bar counts, no special-casing). Emit weights only on those rows, all-NaN elsewhere. Use only data up to and including that close.
- Warm-up: until 253 closes exist, emit 100% BIL on month-end rows (not NaN, so the strategy is not idle cash at 0%).
- BIL is the cash asset and is never ranked. Universes include BIL, so benchmark equal-weight holds 1/(k+1) in BIL, which cushions benchmark drawdown and makes the drawdown margin harder to meet; this is accepted.
- Returns r_k are simple close-to-close returns over k trading days (adjusted closes).

**Common kill / pass rule (per idea, applied to both universes).** For each of the 4 cells (IS, OOS x core, alternate), using the result dict and the benchmark `equal_weight_monthly` of the same universe:
1. `trades` >= 12 in IS and >= 6 in OOS (otherwise the cell cannot support the idea).
2. strategy `sharpe` >= benchmark `sharpe` + 0.10.
3. strategy `max_drawdown` shallower than benchmark's by at least 0.03 (i.e. strategy |max_drawdown| <= benchmark |max_drawdown| - 0.03; check the sign convention when coding).
4. strategy `cagr` >= benchmark `cagr` - 0.03, so a pass cannot come from sitting in cash.
5. Veto: strategy `sharpe` >= (highest Sharpe among all benchmarks present in that run, which includes `sixty_forty` on the core universes) - 0.20.
6. Placebo: the same weights circularly shifted by a random k drawn uniformly from [252, T-252] days against the asset returns, 1000 draws, seed 0, Sharpe metric; percentile of the true Sharpe >= 0.95 in each cell.

SUPPORTED only if all 4 cells pass 1-6. Any miss = REJECTED (a trade-count miss is recorded as "unsupported"). Why equal_weight_monthly: it holds exactly the same assets with a mechanical monthly rebalance, so any edge must come from the timing/selection, not from the asset mix. The 0.10 Sharpe and 3-point drawdown margins are judgement values chosen before looking at data, roughly the size of the noise in a 4-7 year Sharpe estimate.

---

## Idea 1 - Dual momentum: top-2 relative strength with a BIL absolute filter

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 23
- **Strategy file:** TBD

### Hypothesis
Holding the two ETFs with the highest trailing 252-day return among a six-asset risky universe, each only if its 252-day return exceeds BIL's (otherwise that half sits in BIL), rebalanced at month-end, beats the same-universe monthly equal-weight portfolio on Sharpe by at least 0.10 and on max drawdown by at least 3 points in both windows on both universes.

### Why it might work
Antonacci's dual momentum: relative strength (cross-sectional) concentrates in leaders; the absolute filter versus T-bills (time-series) exits assets in downtrends; both rest on the momentum anomalies above. The other side: fixed-allocation holders, rebalancers and benchmark-hugging managers. Parameters: 252 days = Antonacci's 12-month lookback; no skip-month (his convention); top 2 of 6 is my judgement (his original holds 1 of 2 equity indexes, too concentrated for a 6-asset set); BIL as the hurdle is his T-bill rule.

### Rules (exact)
- Risky set R, cash asset BIL. At month-end t with at least 253 closes: score_i = close_t / close_{t-252} - 1, for i in R and for BIL.
- Take the 2 highest-scoring assets in R (ties broken by symbol order). Each gets 0.5 if its score > BIL's score, else its 0.5 goes to BIL. Weights sum to 1.
- Before 253 closes: 100% BIL at month-ends.
- Core universe: R = SPY EFA EEM VNQ TLT GLD, plus BIL. Alternate (shares only BIL): R = QQQ IWM LQD HYG IEF DBC, plus BIL.

### Market conditions needed
Persistent 6-12 month relative leadership (for example equities vs bonds vs gold) and bear markets slow enough for a 12-month return to turn below BIL's within a few months. The 2022 bear (core: TLT and equities fall together, gold and BIL hold) is the key test. Fast crashes and rate-driven leadership flips hurt it; with only two holdings, concentration risk is high.

### How it could fail
Any of the 4 cells fails the common rule. Specific expectation of failure: Sharpe margin missed in either window, or drawdown not 3 points shallower than equal_weight_monthly, or CAGR more than 3 points below it, or placebo percentile < 0.95.

### Test plan
Universes above; benchmark equal_weight_monthly (justified above); 5 bps; IS 2016-01-01..2022-12-31, OOS 2023-01-01..end; placebo as in the common rule. Parameters frozen.

### Results
TBD

---

## Idea 2 - Canary-protected momentum (DAA-style), canaries EEM and AGG

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 24
- **Strategy file:** TBD

### Hypothesis
Holding the top 6 of 11 risky ETFs by 13612W momentum, with a cash fraction in BIL of 0 / 50 / 100% when 0 / 1 / 2 canaries (EEM, AGG) have non-positive momentum, beats the same-universe monthly equal-weight portfolio on Sharpe (+0.10) and drawdown (3 points) in both windows on both universes.

### Why it might work
Keller & Keuning's DAA: the canaries (emerging-market equities as a risk-appetite gauge, aggregate bonds as a rates/credit stress gauge) tend to deteriorate before broad risk assets, so a graded cash fraction avoids part of a drawdown that the risky assets' own rankings would not signal. The 13612W score (weights 12/4/2/1 on 1/3/6/12-month returns) reacts faster than a 12-month SMA. The other side: strategic holders and dip-buyers. Caveats: DAA beat its predecessor on CAGR but with deeper drawdowns in the paper, and results depend on the universe. Parameters: 13612W, top 6 of 12, and EEM/AGG canaries (VWO/BND in the paper) follow the paper. B = 2 (each bad canary raises the cash fraction by 50%) is my deviation: as I recall the headline DAA uses B = 1 (any bad canary means 100% cash); the graded version avoids all-or-nothing switching with so few canaries. I cannot verify the published values from here. EFA stands in for VGK + EWJ, DBC for GSG.

### Rules (exact)
- Score_i = 12*r21 + 4*r63 + 2*r126 + 1*r252 (simple returns, trading-day lookbacks), computed at month-end t with at least 253 closes. A canary is bad when score <= 0.
- b = number of bad canaries; CF = min(1, b/2). Take the 6 highest-scoring risky assets regardless of their sign; each gets (1 - CF)/6; CF goes to BIL.
- Before 253 closes: 100% BIL at month-ends.
- Core: risky SPY IWM QQQ EFA EEM VNQ DBC GLD TLT HYG LQD (11), canaries EEM (also a risky asset) and AGG (not held), plus BIL. Alternate: risky XLE XLK XLV XLF XLU XLP XLY XLI XLB with top 4, canaries EFA and IEF (neither held), plus BIL; the alternate shares only EFA (as a canary) and BIL with the core.

### Market conditions needed
Canary weakness must lead risky-asset losses by weeks, i.e. broad risk-off episodes that start in EM or bonds. 2022 (AGG down alongside equities) is the friendly case; 2020 (a one-month collapse) and any sudden shock not preceded by canary weakness are the hostile cases. A sample with so few distinct drawdowns cannot separate a real leading property of the canaries from luck.

### How it could fail
The common rule on all 4 cells. In particular: if the strategy's drawdown is not 3 points shallower than equal_weight_monthly in any cell, or Sharpe is not +0.10, the protection claim is rejected. On the sector alternate the literature (low OOS Sharpe of sector momentum) suggests the greatest risk of failure.

### Test plan
As in the common rule; benchmark equal_weight_monthly (the idea claims drawdown protection on an equity-heavy basket, and the core universe also reports sixty_forty, used only in the veto, rule 5). Parameters frozen.

### Results
TBD

---

## Idea 3 - Breadth-protected allocation (PAA-style): the universe's own breadth sets the cash fraction

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 25
- **Strategy file:** TBD

### Hypothesis
Holding the top N/2 assets by price-over-252-day-SMA momentum, with the cash fraction BF = min(1, (N - n)/(N/2)) in BIL, where n is the number of the N risky assets above their own 252-day SMA, beats the same-universe monthly equal-weight portfolio on Sharpe (+0.10) and drawdown (3 points) in both windows on both universes.

### Why it might work
Keller & Keuning's PAA: when most assets of a diversified set are in downtrend, the opportunity set for risk is poor and correlations rise, so scaling to cash by breadth gives crash protection without a forecast, and selecting the strongest half retains the upside. Reported: about 10.4% CAGR vs about 8.2% for 60/40 (1993-2015), against a 60/40 benchmark and with costs probably understated early on, and universe-dependent. The other side: static allocators who ignore breadth. The parameters follow the paper: 12-month SMA momentum, protection factor a = 2 (full cash when half the assets are weak), top half selected. Differences from my implementation: a daily 252-close SMA instead of 13 month-end prices, BIL as the only safe asset (the paper picks the best-momentum bond), and the 12-asset set uses EFA, DBC and IEF in place of the paper's regional equity ETFs, GSG and a bond choice.

### Rules (exact)
- At month-end t with at least 252 closes: MOM_i = close_t / mean(close_{t-251..t}) - 1. n = count of risky assets with MOM_i > 0; N = universe size (risky assets only).
- BF = min(1, (N - n)/(N/2)); selected set = the floor(N/2) risky assets with highest MOM_i (regardless of sign); each gets (1 - BF)/floor(N/2); BF goes to BIL.
- Before 252 closes: 100% BIL at month-ends.
- Core: SPY QQQ IWM EFA EEM VNQ DBC GLD HYG LQD TLT IEF (N = 12, top 6) plus BIL. Alternate: XLE XLK XLV XLF XLU XLP XLY XLI XLB (N = 9, top 4) plus BIL; the alternate shares only BIL with the core.

### Differences from ideas 1 and 2
Idea 1 has no breadth dial and holds 2 names; idea 2 reads breadth from two external canaries and uses 13612W; this idea reads breadth from the whole universe using an SMA gap. Because the signals are correlated, a pass for 2 and 3 together is not independent evidence.

### Market conditions needed
Broad, synchronized declines (2022, 2018 Q4) where most assets go below their 12-month average; slowly rising markets otherwise. Failure: a sharp one-month crash from highs (breadth still wide on the last month-end) or a regime where assets fall and rebound one at a time. Because the sample contains one bear year, the real information is weak.

### How it could fail
The common rule on all 4 cells. The sector alternate is the harder cell: all nine sectors move with the equity market, so breadth is effectively a market trend filter, which earlier single-asset trend filters on equities (H1-H16) did not make work.

### Test plan
As in the common rule; benchmark equal_weight_monthly; sixty_forty enters only through the veto on the core universe. Parameters frozen.

### Results
TBD
