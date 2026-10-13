# Round 4: month-end flow ideas from external research (hypotheses 31, 32)

- **Date:** 2026-10-13
- **Ledger hypothesis ids:** 31 (month-end Treasury bid), 32 (pension rebalancing tilt)
- **Strategy file:** `strategies/treasury_month_end_v1.py` (H31), `strategies/pension_tilt_v1.py` (H32); scoring in `research/round4_verdicts.py`, summary in `backtests/round4_summary.json`
- **Source:** "New Trading Ideas — Round 4 Research" (Claude Docs, https://claude.ai/artifact/UWRKnia66kJGerwuqnmk6T), written by another AI from a context prompt that listed H1-H30 and our test protocol. Ideas 1 and 2 of that doc are registered here with their rules as written; reading choices where the doc is silent, and the process changes adopted for this round, are listed below. All of this is fixed before any strategy code is written or any return is computed.

Not in this round: the doc's idea 3 (residual momentum on point-in-time S&P 500 members) will be its own run after this one; its idea 4 (dividend-month premium) is dropped for now (data needs: per-ticker ex-dividend history for about 700 tickers; weakest prior).

Multiple-testing count: these are hypotheses 31 and 32. Thirty ideas have been tested before them, all rejected or (H1) unresolved.

## Process changes adopted for this round (decided before testing)

From the doc's process critique, applied to H31 and H32 only (earlier verdicts are not re-scored):
1. **Delayed-fill robustness.** Both ideas hold for 5 days or fewer, and our fill at the signal day's close can flatter short holds. Each idea is also run with every target one trading day late (decided at close t, traded at close t+1). In every cell, the mean net (H31) or signed (H32) edge per event under the delayed fill must stay above 0.
2. **Overlay yardstick.** H32 is judged on net active return and per-event edge against its untilted 60/40, not on a Sharpe gap (its rule below already does this).
3. **Second null for the conditional rule.** H32 must also beat a month-level sign shuffle that keeps the calendar and randomises the tilt direction, in addition to the 252-day circular shift.
4. **Running count** of hypotheses tested, stated above and in the verdicts.

Not adopted this round, noted for later: a pooled panel test across near-duplicate symbols, an IS t-stat hurdle of 3, and a forward paper-trading holdout (that needs the dry-run runner).

## Idea 1 (H31): month-end Treasury index-extension bid

### Hypothesis
Long-duration Treasury ETFs earn their excess return mostly over the last three trading days of the month, because index-benchmarked holders must buy duration when Treasury indices extend at the month-end rebalance; holding only over those days earns at least 10 bps net per event and at least 5 bps per day more than buy-and-hold's mean day.

### Rule (exact)
- T = the last scheduled NYSE trading day of the month (`core.market_calendar`).
- Weight 1 at the closes of T-3, T-2 and T-1, so the position earns the returns of T-2, T-1 and T. Weight 0 at the close of T and on every other day. Cash earns 0% (round trip 10 bps). No warm-up.
- Tickers: VGLT, SPTL, EDV, ZROZ, TLH (all listed before 2016).
- Secondary line, reported only: the same rule holding BIL when out of the Treasury ETF.

### Why it might work
Bloomberg Treasury indices add new issues only at the month-end rebalance, so index duration jumps then; benchmarked managers and life insurers buy at that close to limit tracking error. Dealer balance sheets are tightest at month-end, which limits who can take the other side.

### Evidence (as reported in the doc)
- Hartley & Schwarz (2019), 1990-2018, full text checked by the doc's author: the 10-year zero earns +0.25% per month over the last 3 days (Sharpe 0.88); other days are not significant; the 2015-2019 subsample is still +0.27% and significant. https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2019/12/17-19.Schwarz.pdf
- Harvey, Mazzoleni & Melone (2026 revision): 10-year note futures earn about +4 bps per day in the last week of the month, 1997-2023.
- Against: CXO Advisory's TLT test since 2002 did not corroborate the paper. https://www.cxoadvisory.com/bonds/term-premium-end-of-month-effect/

### How it could fail (kill rule, per symbol and window; benchmark buy-and-hold of the same ETF)
A cell supports only if all hold:
- mean net return per event (the event's three daily net returns plus the exit-day cost) >= +10 bps;
- return per exposure day >= buy-and-hold mean daily return + 5 bps;
- placebo (`core.verdicts.placebo_percentile`, return_per_exposure_day, 1000 shifts, seed 0, min shift 252) >= 0.95;
- delayed-fill mean net return per event > 0.
Fewer than 60 events in-sample or 36 out-of-sample: inconclusive. Supported only if at least 4 of 5 symbols pass both windows. The five ETFs are near-copies of one another, so a pass is closer to one test than five; this is stated rather than corrected.

Prior: medium-low (the doc's own). The mechanism is strong and well known to bond desks; the 2002+ TLT result is a warning. The 2023-onward window has been seen for TLT in earlier rounds, and these ETFs move with it.

### Results
**Rejected.** 3 of 10 cells pass; 0 of 5 ETFs pass both windows (4 needed). 84 events in-sample, 45 out-of-sample for every ETF.

| ETF | Window | Mean net / event | Delayed fill | Hit rate | Return / exposure day vs B&H mean | Placebo | Cell |
|---|---|---|---|---|---|---|---|
| VGLT | IS | 0.273% | -0.007% | 61% | 0.091% vs 0.002% | 0.99 | fails (delayed fill) |
| VGLT | OOS | 0.075% | 0.113% | 58% | 0.025% vs -0.002% | 0.85 | fails (edge, per-day, placebo) |
| SPTL | IS | 0.270% | -0.008% | 62% | 0.090% vs 0.002% | 0.99 | fails (delayed fill) |
| SPTL | OOS | 0.072% | 0.108% | 58% | 0.024% vs -0.002% | 0.85 | fails (edge, per-day, placebo) |
| EDV | IS | 0.359% | 0.006% | 58% | 0.120% vs 0.001% | 0.99 | passes |
| EDV | OOS | 0.032% | 0.099% | 58% | 0.010% vs -0.017% | 0.76 | fails (edge, per-day, placebo) |
| ZROZ | IS | 0.436% | 0.015% | 61% | 0.146% vs 0.004% | 0.99 | passes |
| ZROZ | OOS | -0.002% | 0.140% | 56% | -0.001% vs -0.024% | 0.72 | fails (edge, per-day, placebo) |
| TLH | IS | 0.197% | 0.000% | 61% | 0.066% vs -0.002% | 1.00 | passes |
| TLH | OOS | 0.085% | 0.137% | 58% | 0.028% vs 0.002% | 0.86 | fails (edge, per-day, placebo) |

What this says:
- In-sample (2016-2022) the effect is clearly there: 20-44 bps net per event, placebo 0.99-1.00, in line with the paper's +25 bps a month. Over the whole window, which ends with the 2022 bond crash, the timed line compounded 2-5% a year while buy-and-hold lost 0.5-1.5% a year.
- In-sample, a one-day-late fill erases it (about 0 per event). The edge sits in the exact last-three-day window, which is what the mechanism predicts but leaves no room for execution slippage.
- Out-of-sample (2023 onward) it fades to 0-9 bps per event and the placebo drops to 0.72-0.86. Odd detail: the delayed-fill version does better OOS (about 10-14 bps), which hints the bid may have moved later (into the first day of the next month), or is noise. That was not a pre-set rule, so it is not tested here; it would have to be a new hypothesis with its own fresh data.
- The BIL variant (reported only) had Sharpe 0.46-0.98 OOS, mostly from T-bill carry while out of the Treasury ETF.

### Note on implementation
None beyond the reading choices below; the code was committed (e13c628) before any result was computed.

## Idea 2 (H32): pension rebalancing tilt

### Hypothesis
In the last week of the month, after equities have beaten bonds month-to-date, calendar rebalancers sell equities and buy bonds, so tilting a 60/40 portfolio against the month-to-date winner earns at least 20 bps per event and a positive net active return against the untilted 60/40.

### Rule (exact)
- Universes (equity, bond): (VTI, IEI), (VTI, VGIT), (VEA, IEI).
- R_e and R_b: total returns of the equity and bond ETF from the previous month's last close to close t. Calendar signal C_t = 0.6(1+R_e) / (0.6(1+R_e) + 0.4(1+R_b)) - 0.6 (the drift of a 60/40 portfolio since the last month-end).
- Signal days are T-5 to T-1 (T = last scheduled trading day of the month), so tilts earn days T-4 to T.
- On a signal day with |C_t| >= 0.33 percentage points (0.0033): equity weight = 0.6 - 0.2 x sign(C_t), bond weight = 1 - equity weight.
- At the close of T, and on every other day, hold 60/40, rebalanced at month-end like the benchmark. The paper's first-day reversal leg is dropped.
- Benchmark: static 60/40 of the same two ETFs, rebalanced at each month-end, same costs.

### Why it might work
Pensions, target-date and balanced funds hold fixed targets and trade them on a schedule; the paper estimates their beneficiaries lose about $16 billion a year to this predictability. Harvey, Mazzoleni & Melone, NBER w33554, January 2026 revision (full text checked by the doc's author): 1997-2023, a one-sd calendar signal predicts -17 bps in equities and +2 bps in bonds the next day, concentrated at month-end; absent in 1961-1997; their futures long-short version earns about 10% a year at Sharpe about 1. https://www.nber.org/papers/w33554

### How it could fail (kill rule, per universe and window)
A cell supports only if all hold:
- mean signed equity-minus-bond return over the held tilt days >= +20 bps per event (an event is a month with at least one tilt; signed means -sign(C) x (equity return - bond return), summed over that month's tilted days, gross of costs);
- annualized net active return against the benchmark (mean daily strategy minus benchmark return x 252) > 0;
- placebo, both nulls >= 0.95 on the annualized active return: (a) the active weight and its costs circularly shifted by at least 252 days, 1000 draws, seed 0; (b) the tilt direction flipped at random month by month, 1000 draws, seed 0;
- delayed-fill mean signed return per event > 0.
Fewer than 30 events in-sample or 15 out-of-sample: inconclusive. Supported only if all three universes pass both windows.

Prior: medium-low (the doc's own). Our in-sample window sits inside the paper's sample, so it is a replication, not a test; the long-only tilt captures a slice of a long-short effect; edge-to-cost is about 2:1 at the threshold; returns are lumpy.

### Results
**Rejected.** 1 of 6 cells passes (VEA/IEI out-of-sample); all six were needed.

| Universe | Window | Events | Mean signed / event | Delayed fill | Hit rate | Net active / yr | Shift placebo | Sign-shuffle placebo | Cell |
|---|---|---|---|---|---|---|---|---|---|
| VTI/IEI | IS | 76 | 0.375% | 0.030% | 57% | +0.40% | 0.968 | 0.933 | fails (shuffle) |
| VTI/IEI | OOS | 42 | 0.191% | -0.001% | 55% | -0.01% | 0.834 | 0.765 | fails (all five) |
| VTI/VGIT | IS | 75 | 0.388% | 0.078% | 59% | +0.44% | 0.969 | 0.938 | fails (shuffle) |
| VTI/VGIT | OOS | 42 | 0.166% | 0.048% | 55% | -0.08% | 0.811 | 0.730 | fails (edge, active, both placebos) |
| VEA/IEI | IS | 78 | 0.373% | -0.258% | 58% | +0.42% | 0.948 | 0.946 | fails (both placebos, delayed fill) |
| VEA/IEI | OOS | 40 | 0.392% | 0.369% | 55% | +0.39% | 0.953 | 0.956 | passes |

What this says:
- In-sample it nearly replicates the paper: about 37-39 bps per tilt month and +0.4% a year net active, but the month-level sign shuffle (the new second null) is not convinced (0.93-0.95). The direction of the tilt adds only a little beyond being tilted at all at month-end.
- On US equities out-of-sample the edge halves and net active goes to zero. Only VEA/IEI holds up OOS, and its in-sample cell fails, including a strongly negative one-day-late version (-26 bps); VEA prices partly stale foreign closes, so a one-day lag changes what it measures.
- The size is small even where it works: +0.4% a year on a 60/40, about 2:1 edge-to-cost at the threshold, as the memo warned.

### Note on implementation
The placebo statistic uses the held equity weight minus the benchmark's held equity weight (both drift between trades) rather than "held weight minus 0.6"; with two assets and no cash this makes the statistic equal the scored net active return exactly (the script asserts this). Tilt days and their sign for the per-event numbers come from the targets, as written in the rule. This was settled before the run (commit e13c628).

## Reading choices (where the doc is silent)
- H32, below-threshold signal days: if the previous day carried a tilt, the portfolio returns to 60/40 that day; otherwise there is no trade, so the portfolio drifts exactly like the benchmark. The tilt is re-decided every signal day from that day's C_t.
- H32 starts at 60/40 on the first bar, like the benchmark; no tilt can occur until a previous month-end exists.
- Placebo statistics for H32 are computed in active-return space: active weight on equities (held equity weight minus 0.6) times the equity-minus-bond return, minus that day's tilt-trading cost.
- The delayed-fill variants shift every target by one trading day; for H31 that means holding over T-1, T and the first day of the next month.

## Round summary
Both rejected. Hypotheses tested so far: 32; none supported. Both effects look real in 2016-2022 (inside the papers' samples) and weaken sharply from 2023, matching the pattern in H24, H25 and H28. Next is the doc's idea 3 (residual momentum on point-in-time S&P 500 members) as its own run.
