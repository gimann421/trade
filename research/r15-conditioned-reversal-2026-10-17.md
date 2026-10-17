# Round 15: reversal conditioned on 52-week high, medium-term trend and volatility (2026-10-17)

Source of the ideas: `research/deep-research-round3-conditioning-ideas-2026-10-17.md` (project folder; ranked report).
Garret asked on 2026-10-17 to research further and then test. Hypotheses 139-141; 138 were tested before this round.

**This section is written before any result of these rules was computed.**

## Parent and what is varied
Parent: `rev5_h3_band40_s` (every 3 sessions, minus the 5-day return, top 10% of ranked point-in-time S&P 500 members with a
keep-while-top-40% band, equal weight, 5 bps; fill at the close). A filtered rule ranks **only the names in one half** of
the ranked names, split at the cross-sectional median of a filter variable on each decision day; the book is 10% of that
half, the band 40% of that half (the same way round 13 filtered). Filter variables, all known at the decision:
- **F1, distance from the 52-week high:** price now / highest daily close of the previous 252 sessions (at least 200 present).
  Tested half: **below the median (far from the high)**.
- **F2, medium-term trend:** close 21 sessions ago / close 252 sessions ago (the 12-1 month return, at least 200 sessions of
  history). Tested half: **below the median (medium-term losers)**.
- **F3, volatility:** standard deviation of daily close-to-close returns over the previous 60 sessions. Tested half:
  **below the median (low volatility)**. The literature disagrees on direction, so the high-volatility half is reported
  with the same numbers.
- The opposite half of every filter is **report-only** (never a hypothesis); if it passes the whole bar it is noted as a lead.

## Three evaluations, all must pass
1. **Screen, all members (about 719 names), daily-close timing:** signal read at the official close, fill at the close.
   The 15:45 snapshots exist only for a 300-name sample, so the full set can only be run this way.
2. **Screen, the roughly 419 names outside the snapshot sample:** the same, restricted to them (the "unseen" names).
3. **Snapshot run, the 300-name sample:** signal read at the 15:45 price (F1's numerator too), fill at the close, as in
   round 9; also at 10 bps and with the 15:30 price.
Each evaluation has its own unfiltered parent on the same names and timing. A screen pass alone is only "testing"; a rule is
"supported" only if all three pass.

## Bar (per evaluation, in both windows IS 2017-2022 and OOS 2023 on)
Net active vs the equal-weight members >= 2.0%/yr, information ratio >= 0.3, selection placebo >= 0.95 (1,000 random baskets
of the same size from the ranked names, seed 0), positive at 10 bps, **and net active above the evaluation's own unfiltered
parent in both windows**; the snapshot run also needs a positive net active with the 15:30 price. Decision counts: at least
160 (IS) and 100 (OOS). The data were downloaded afresh in this session; the parent's numbers may differ a little from
earlier memos and the parent here is the comparison that counts.

## Known limits
- Hypothesis count after this round: 141. About 7 of 141 are expected to pass a 5% test by chance; the placebo, the
  beat-the-parent rule and the three evaluations are the guard.
- Members that left the index have daily bars (Alpaca's `asof` renames), so there is no survivorship cut in prices; the
  screens are still daily-close, not executable.
- Halving the ranked names makes the book more concentrated (about 25 names in the snapshot sample), so turnover and noise rise.

## Results
(to be added)
