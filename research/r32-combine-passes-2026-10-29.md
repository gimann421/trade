# Round 32: combining the two passes (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 203-205; 202 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged. No new data is fetched.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Low accruals (round 25) and R&D intensity (round 28) are the only two rules that cleared the bar, and their monthly active returns correlate at 0.36. Natural branches off proven rules, each fully specified here before running:
- **203 `combo_rank_quintile`**: average of the cross-sectional percentile ranks of minus-accruals (higher = better) and R&D / assets, among names scored on both; hold the top 20%.
- **204 `rnd_in_lowacc_half`**: among names scored on both, keep the half with lower accruals (higher minus-accruals score), then hold the top 20% of that half by R&D / assets (about 10% of scored names).
- **205 `lowacc_in_rnd_names`**: among names scored on both, hold the 20% with the lowest accruals. This asks whether the accruals effect works inside the R&D-reporting group, which is mostly tech and health care; it is the accruals rule restricted to that sector-like group.

## Common setup
Round 25-31 setup exactly (annual first-filed 10-K values usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, equal weight, benchmark equal-weight names scored on both, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names).

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Because each is a branch off a proven rule, a pass also needs an information ratio above the better of its parents' on the same set of names, in both windows (parents: R&D quintile and low-accruals quintile, both built on the names scored on both). Reported, not judged: mirrors; the tech/health share of the picks; correlation of the monthly active return with each parent.

## Multiple testing
Three rules, no variants. Total tested after this round: 205. These are the same two signals in new combinations, so they are far from independent of the earlier passes; a combined rule that "passes" is not additional evidence for either parent.

## Results (run 2026-10-29)

**Verdict: all three rejected (hypotheses 203-205).** Tests after this round: 205. `backtests/round32_tests/`. Names scored on both signals: 69 in early 2017, 169 at the end (so quintiles hold 14 to 34 names).

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on; all on the names scored on both signals:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| Parent: R&D quintile | +4.6% (0.41, 0.98) | +17.8% (1.59, 1.00) | reference |
| Parent: low-accruals quintile | +4.3% (0.60, 0.98) | +5.6% (0.71, 0.97) | reference |
| 203 average rank of both | +1.3% (0.13, 0.65) | +12.6% (1.17, 1.00) | rejected: weak in 2017-22, below both parents |
| 204 R&D within lower-accruals half | +1.4% (0.15, 0.69) | +11.7% (1.10, 1.00) | rejected: same |
| 205 lowest accruals within R&D names | +4.3% (0.60, 0.98) | +5.6% (0.71, 0.97) | rejected: not above the R&D parent's information ratio |

Design flaw to note: 205 is identical to the low-accruals parent on this name set by construction (the parent is built on the same names), so its comparison with that parent is empty; it fails only because it is below the R&D parent's information ratio (OOS 0.71 against 1.59) under the pre-registered "better of both parents" rule. Against the original all-names low-accruals rule (IR 0.51 / 0.60) it is higher, which is a diagnostic, not a pass.

Correlation of monthly active return: 203 with R&D 0.82 and accruals 0.60; 204 with R&D 0.83 and accruals 0.48; 205 with R&D 0.33. Mean tech/health share of picks: 99%, 99%, 78%. Mirror of 203 (worst average rank): -6.1% / -6.0%.

### Plain English
- **Mixing the two winning rules** did not help. Companies that are both low in accruals and heavy on R&D did worse in 2017-22 than either rule alone, and gave up part of the recent R&D gain. The two rules pick different kinds of companies, and the overlap is the weak spot.
- **Low accruals within research-heavy companies** earned about +4.3%/yr then +5.6%/yr, so the accruals edge is not just a sector effect: it holds even among tech and health-care names. That backs up low accruals (diagnostic, found after the fact).
- No new rule. Still two: low accruals and R&D intensity.
