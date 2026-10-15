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
(to be filled after the runs)
