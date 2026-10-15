# Round 11: cutting cost and sharpening the signal of the reversal rule (hypotheses 112-120)

- **Date:** 2026-10-15
- **Plan:** Phase 2 of the round-10 research plan, approved in the thread on 2026-10-15 ("let's keep going")
- **Ledger hypothesis ids:** 112-120, titles "Short-horizon v4: <rule id>". The gap-fade screens (B4) are report-only unless they pass their screen.
- **Strategy file:** `strategies/short_horizon_v4.py`; scoring in `research/round11_ideas.py`; industry codes from `core/industry.py`, earnings dates from `core/edgar.py`.
- **What was known when this was written:** rounds 1-10 in full. 111 hypotheses tested. The round-10 neighbours showed the band rule's edge is positive in every variant but passes the bar only where costs bite least: `rev5_h3_band40_s` (5-day reversal, decide every 3 sessions, hold the top 10% and keep a name while it is in the top 40%) passed the full bar on the 300-name sample, on the 418 other names and on all 718 together (net active +7.9% / +4.9% on all names, 10 bps +4.4% / +1.4%). The round-9 shadow rule `rev5_h2_band_s` passes on two of the three universes. The era work suggested the effect is stock-specific, not an industry or sector effect. No return of any rule below has been computed.

## Universe, timing, bar
Universe: all 718 point-in-time S&P 500 members with 15:45 snapshots (the 300-name round-9 sample plus the other 418), run on all together and then on the 418 names alone. Timing, costs, windows, March 2020 handling and the bar are exactly those of rounds 9 and 10: 15:45 price on the decision day, fill at the official close, 5 bps on turnover; net active >= 2% a year, IR >= 0.3, placebo >= 0.95 in each of 2017-2022 and 2023 on; positive at 10 bps; positive with the 15:30 signal where the rule uses the 15:45 price (for the last-15-minutes rules, which use both prices, the check is replaced by the rule's own sign test, see B3). Minimum decisions 250 / 150 for hold 2 and 150 / 100 for hold 3.

**Raised bar for a pass, set because 120 hypotheses will have been tested:** a rule is **supported** only if it passes the full bar on all 718 names **and** on the 418 names that were not in the round-9 sample. A pass on all 718 alone is reported but stays `testing`.

Every rule is also compared with its parent: net active and 10 bps net active, minus the parent's, per window. The parents are `rev5_h3_band40_s` (hold 3, band 40%, book 10%) and `rev5_h2_band_s` (hold 2, band 30%, book 10%). Improving on a parent is not a bar condition; it is reported so that a pass that merely matches the parent is not mistaken for progress.

## Rules (exact)

**A1. Do not top up (turnover).** After each decision, names kept from the previous book keep their drifted weight instead of being rebalanced to equal weight; the proceeds of the names sold are split equally among the names bought. If no name is bought the kept weights are scaled to sum to 1. Rules: `rev5_h3_band40_nt_s` (parent `rev5_h3_band40_s`), `rev5_h2_band_nt_s` (parent `rev5_h2_band_s`).

**A2. Blend two signals.** Score = z-score of `rev5` plus z-score of `id5` (minus the sum of the last 5 intraday log returns, the last one measured to the 15:45 price), z-scores taken across the ranked names at the decision date; a name is ranked only if both exist. Hold 3, band 40%, book 10%. Rule: `blend_h3_band40_s` (parent `rev5_h3_band40_s`).

**B1. Industry-neutral reversal.** Score = minus (the name's 5-day return to the 15:45 price minus the mean 5-day return of the ranked names in its SIC two-digit major group). A group with fewer than 5 ranked names, and any name with no SIC code (all names no longer in the index have none), uses the mean of all ranked names instead. Rules: `rev5n_h3_band40_s`, `rev5n_h2_band_s` (parents as above).

**B2. Skip names with a fresh earnings release.** `rev5` ranking, but a name is not ranked if an earnings release (8-K Item 2.02) has its reaction session within the 5 sessions ending on the decision day (releases accepted after the close of the decision day have a later reaction session and are not visible). Earnings dates exist only for current members; a name without any is never excluded. Rules: `rev5x_h3_band40_s`, `rev5x_h2_band_s`.

**B3. The last 15 minutes.** Score = plus or minus the return from the 15:30 price to the 15:45 price on the decision day. `l15rev_h2_band_s` buys the names that fell most in that window (score = minus the return); `l15mom_h2_band_s` buys the names that rose most. Hold 2, band 30%, book 10%. The 15:30-signal check does not apply (the rule needs both prices); in its place the rule must pass the full bar with the sign of the score flipped being strictly worse in net active in both windows, i.e. the direction is not arbitrary.

**B4. Gap fade on stocks (report-only screen, daily bars).** Each session, buy at the open the top 10% of members by minus the overnight return (open over previous close), equal weight, sell at the close; benchmark the equal-weight members over the same open-to-close interval. Reported: annualized gross active return per window (before any cost). It advances to a full pre-registration only if gross active is at least 25% a year in both windows (the round-trip cost of 10 bps a day is about 25% a year); otherwise it stops here and is not a hypothesis. A second screen applies the same rule only to names with a gap of at least 2% in either direction.

## Kill and reporting rules
- Any rule whose gross active return is under 4% a year in both windows is not described as a candidate even if the bar is met by luck of the cost line.
- Not tested here: anything in rounds 1-10 re-run; changes to the shadow record; new data beyond industry codes and earnings dates.
- Every rule is reported with its parent comparison, break-even cost, turnover, weeks to a t-statistic of 2, and the same table for the 418-name universe.

## Limits
Industry codes and earnings dates exist only for current members, so B1 and B2 act only on part of each date's universe in earlier years (survivorship in the tagging, not in the prices); the 718 names include the 300 whose snapshots the round-9 pass was found on, which is why the raised bar looks at the 418 separately; flat 5 bps; closing-auction competition not modelled.

## Results

Run 2026-10-15 on the commit that adds this section. Statuses set by `research/round11_ideas.py --finalize`. The parent rows reproduce the round-10 numbers exactly (all names: +7.9% / +4.9% for `rev5_h3_band40_s`).

**Verdict: 0 of 9 pass the raised bar (all 718 names and the 418 unseen). All nine are marked rejected. Hypotheses tested: 120.**

### All 718 names

| Rule | Net active IS / OOS | IR IS / OOS | At 10 bps IS / OOS | 15:30 signal IS / OOS | Turnover IS / OOS | Verdict IS / OOS |
|---|---|---|---|---|---|---|
| rev5_h3_band40_s | +7.9% / +4.9% | 0.62 / 0.39 | +4.4% / +1.4% | +7.6% / +5.8% | 71 / 70 | supports/supports |
| rev5_h2_band_s | +5.7% / +4.6% | 0.42 / 0.35 | +1.0% / -0.1% | +5.2% / +4.7% | 94 / 93 | supports/contradicts |
| rev5_h3_band40_nt_s | +8.5% / +4.2% | 0.65 / 0.35 | +5.0% / +0.8% | +7.6% / +5.0% | 70 / 69 | supports/supports |
| rev5_h2_band_nt_s | +5.5% / +3.4% | 0.40 / 0.25 | +1.0% / -1.1% | +5.2% / +4.7% | 92 / 91 | supports/contradicts |
| blend_h3_band40_s | +4.5% / +2.8% | 0.35 / 0.22 | +1.1% / -0.6% | +4.4% / +3.0% | 70 / 69 | supports/contradicts |
| rev5n_h3_band40_s | +6.6% / +1.4% | 0.57 / 0.14 | +3.2% / -2.0% | +7.2% / +2.2% | 71 / 69 | supports/contradicts |
| rev5n_h2_band_s | +5.7% / +6.0% | 0.47 / 0.54 | +1.0% / +1.4% | +6.1% / +5.3% | 93 / 92 | supports/supports |
| rev5x_h3_band40_s | +7.5% / +3.5% | 0.57 / 0.26 | +3.8% / -0.3% | +8.1% / +4.6% | 75 / 76 | supports/contradicts |
| rev5x_h2_band_s | +4.9% / +4.4% | 0.35 / 0.32 | -0.1% / -0.6% | +4.2% / +4.9% | 99 / 101 | contradicts/contradicts |
| l15rev_h2_band_s | -9.2% / -1.5% | -0.90 / -0.15 | -17.7% / -9.9% | n/a / n/a | 170 / 169 | contradicts/contradicts |
| l15mom_h2_band_s | -5.4% / -7.8% | -0.62 / -0.86 | -14.0% / -16.3% | n/a / n/a | 172 / 170 | contradicts/contradicts |

### The 418 unseen names

| Rule | Net active IS / OOS | IR IS / OOS | At 10 bps IS / OOS | 15:30 signal IS / OOS | Turnover IS / OOS | Verdict IS / OOS |
|---|---|---|---|---|---|---|
| rev5_h3_band40_s | +7.9% / +4.8% | 0.61 / 0.37 | +4.4% / +1.3% | +7.4% / +3.2% | 71 / 71 | supports/supports |
| rev5_h2_band_s | +4.9% / +4.9% | 0.37 / 0.37 | +0.2% / +0.3% | +4.6% / +5.3% | 95 / 94 | supports/supports |
| rev5_h3_band40_nt_s | +7.3% / +4.1% | 0.55 / 0.33 | +3.9% / +0.7% | +7.7% / -1.2% | 70 / 69 | supports/contradicts |
| rev5_h2_band_nt_s | +3.9% / +0.2% | 0.28 / 0.02 | -0.6% / -4.3% | +2.7% / +7.1% | 92 / 92 | contradicts/contradicts |
| blend_h3_band40_s | +4.8% / +0.2% | 0.37 / 0.02 | +1.3% / -3.2% | +5.0% / +1.3% | 70 / 70 | supports/contradicts |
| rev5n_h3_band40_s | +5.6% / -1.6% | 0.46 / -0.15 | +2.1% / -5.0% | +7.3% / -1.8% | 71 / 69 | supports/contradicts |
| rev5n_h2_band_s | +4.6% / +4.7% | 0.37 / 0.42 | -0.1% / +0.1% | +5.6% / +5.6% | 93 / 92 | contradicts/supports |
| rev5x_h3_band40_s | +5.3% / +2.4% | 0.40 / 0.18 | +1.6% / -1.4% | +5.7% / +0.6% | 75 / 77 | supports/contradicts |
| rev5x_h2_band_s | +3.7% / +6.5% | 0.27 / 0.47 | -1.3% / +1.3% | +3.3% / +5.6% | 100 / 103 | contradicts/supports |
| l15rev_h2_band_s | -5.9% / +1.0% | -0.60 / 0.09 | -14.4% / -7.5% | n/a / n/a | 171 / 170 | contradicts/contradicts |
| l15mom_h2_band_s | -6.3% / -6.3% | -0.71 / -0.66 | -14.9% / -14.8% | n/a / n/a | 172 / 170 | contradicts/contradicts |

### What each idea did
- **A1 do not top up.** Hold 3 is better in the first window and worse in the second; hold 2 is worse in both. Turnover barely moves (70 vs 71, 92 vs 94 trades a year), because the band already keeps most names. Not a cost fix. The hold-3 version passes on all 718 but fails the 15:30 check on the unseen names (second window -1.2%).
- **A2 blend with the intraday signal.** Worse than the parent in both windows and both universes; adding the second signal dilutes the first.
- **B1 industry-neutral.** Mixed. Hold 3 collapses in the second window (+1.4% on all names, -1.6% on the unseen names). Hold 2 is the best second-window number of the round (+6.0% all, +4.7% unseen) but the first window fails on the unseen names (10 bps -0.1%), so it does not hold up across both. Not stable enough to count.
- **B2 skip fresh earnings.** No consistent gain over the parent (hold 3 is lower in both windows, hold 2 is higher in one window on the unseen names only). Excluding names with a recent release does not raise the net result, so the edge is not an earnings-announcement artifact.
- **B3 last 15 minutes.** Neither direction works. Both signs lose money net of costs (turnover about 170 a year), and both are far from the parent, so this is not a usable signal.
- **B4 gap fade (screen, no hypothesis).** Gross active +9.6% / +16.0% a year on all names (needs 25% in both windows to advance) and negative on gaps of 2% or more. Stops here.

### Conclusion
Nothing improves on `rev5_h3_band40_s`, which stays the lead (not formally supported). The thinness of the edge at 10 bps is not fixed by trading less, by neutralising industry, or by skipping earnings. The shadow record `stock_rev5_h2_band` is unchanged.
