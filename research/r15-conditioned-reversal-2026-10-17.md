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

## Results (run 2026-10-17)

**Verdict: 0 of 3 supported, all three rejected** (`backtests/round15_filters/`). Hypotheses tested after this round: 141. Nothing
is added to the shadow or paper records. Net active per year vs the equal-weight members, 5 bps, IS 2017-2022 / OOS 2023 on;
"opposite half" is report-only.

| Evaluation | Rule | Net active IS / OOS | IR IS / OOS | Placebo IS / OOS | 10 bps IS / OOS | Opposite half IS / OOS |
|---|---|---|---|---|---|---|
| Screen, all 719 names | parent | +6.2% / +0.3% | 0.47 / 0.02 | 1.00 / 0.94 | +2.7% / -3.1% | |
| | 139 far from 52-week high | +5.2% / +0.3% | 0.30 / 0.02 | 0.97 / 0.76 | +1.4% / -3.5% | +0.3% / -5.3% |
| | 140 medium-term losers | +10.7% / -9.5% | 0.65 / -0.68 | 1.00 / 0.12 | +7.2% / -13.1% | +2.0% / +9.4% |
| | 141 low volatility | +1.8% / -5.6% | 0.20 / -0.62 | 1.00 / 0.86 | -1.9% / -9.4% | +8.8% / +4.9% |
| Screen, 419 unseen names | parent | +5.2% / -0.8% | 0.40 / -0.07 | 1.00 / 0.79 | +1.8% / -4.2% | |
| | 139 | +2.6% / -1.3% | 0.16 / -0.08 | 0.77 / 0.49 | -1.2% / -5.1% | -3.2% / -0.8% |
| | 140 | +10.7% / -7.3% | 0.66 / -0.51 | 1.00 / 0.25 | +7.0% / -11.0% | -0.6% / +11.3% |
| | 141 | +1.1% / -7.3% | 0.12 / -0.75 | 1.00 / 0.67 | -2.6% / -11.0% | +5.2% / +5.9% |
| Snapshot, 300 names | parent | +9.9% / +3.0% | 0.69 / 0.21 | 1.00 / 0.95 | +6.4% / -0.4% | |
| | 139 | +12.1% / +8.0% | 0.61 / 0.37 | 1.00 / 0.98 | +8.2% / +4.2% | +3.0% / -3.3% |
| | 140 | +12.0% / -9.3% | 0.62 / -0.52 | 1.00 / 0.34 | +8.4% / -13.0% | +1.5% / +9.2% |
| | 141 | +0.4% / -4.3% | 0.04 / -0.39 | 0.95 / 0.74 | -3.3% / -8.0% | +14.4% / +6.2% |

Why each fails the pre-registered bar:
- **139, far from the 52-week high:** passes only on the 300-name snapshot sample (12.1% and 8.0%, both above the parent and
  the bar, 15:30 signal positive). It fails on all 719 names and on the 419 names outside the sample (OOS +0.3% and -1.3%),
  so the sample result does not generalise. Rejected.
- **140, medium-term losers:** the best first window of the round (+10.7% to +12.0%, IR 0.62 to 0.66) and the worst second
  window (-7% to -9%). The opposite half, medium-term winners, flips the other way (+9.4% to +11.3% since 2023, +1.5% to +2.0%
  before). Rejected.
- **141, low volatility:** below the parent everywhere; the high-volatility half (opposite) is the better one in both windows
  in the snapshot sample (+14.4% / +6.2%), the Medhat and Novy-Marx direction. Rejected as registered.

Plain English: none of the three conditions makes the reversal rule reliably better. The two "mirror" results are interesting but
were not pre-registered: the high-volatility half did as well as or better than the whole rule in both windows on all three evaluations
(+8.8 / +4.9, +5.2 / +5.9, +14.4 / +6.2), and since 2023 the reversal profit sits in medium-term winners, not losers.
Treat both as leads, not results: they are the opposite halves of tests that failed, found after the fact, and the winner/loser
flip around 2023 matches the regime change round 13 saw in its filters. Neither can be confirmed without a second era (Sharadar).
