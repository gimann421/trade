# Round 16: ideas from the fourth deep-research report (2026-10-17)

Source of the ideas: `research/deep-research-round4-outside-the-box-2026-10-17.md` (project folder). Garret said "Test all 3"
on 2026-10-17: ideas 1 to 3 of that report. Hypotheses 142-144; 141 were tested before this round.

**This section is written before any result of these rules was computed.**

## Common set-up
- Windows: IS = 2017-2022, OOS = 2023 on (daily rules decide from 2017-01-03, the monthly rule from 2017-01-31). Data as in
  earlier rounds: Alpaca daily bars, adjusted; point-in-time S&P 500 members for the stock rules.
- Bar, as in rounds 13 to 15: in **both** windows net active return vs the benchmark >= 2.0%/yr, information ratio >= 0.3,
  selection placebo >= 0.95 (1,000 random baskets from the same ranked names, seed 0), and positive net active at the stress cost.
  March 9 to 20, 2020 is excluded from the daily rules as before (bad ticks). Minimum decisions: 160 (IS) / 100 (OOS) for the
  3-session rules, 48 / 36 for the monthly rule.
- Any cell short of its minimum is "inconclusive"; a rule is "supported" only if every cell supports it.

## Test 1: filing-language change (hypothesis 142), `filing_stable_q_m`
Idea: companies that rewrite their annual and quarterly reports a lot earn less afterwards than companies that leave the
wording alone (Cohen, Malloy and Nguyen, "Lazy Prices").
- **Covered set:** current S&P 500 members (CIK from the constituent file, as in `core/edgar.py`) that are also point-in-time
  members at the decision date. Past members have no CIK in our files, so they are not covered. Because covered names are
  survivors, the **benchmark is the equal-weight of the covered names that have a score that month**, never all members.
- **Filings:** Forms 10-K and 10-Q from the SEC archive (no amendments), 2015 on. Text: HTML tags and tables removed,
  lower-cased, alphabetic words of at least 2 letters. Score = cosine similarity of the word-count vectors of the latest filing and the
  same form's filing one year earlier (10-K vs prior 10-K; 10-Q vs the 10-Q whose report date is 365 +/- 45 days earlier). A name is
  scored on a decision date only if the latest such filing was accepted by 16:00 New York time of that date and within the last
  100 calendar days.
- **Rule:** at each month end, hold the 20% of scored names with the **highest** similarity, equal weight, to the next month
  end, 5 bps (stress 10 bps).
- Report only: 10-K-only version; Jaccard similarity of word sets; the 20% with the lowest similarity ("changers").
- Known limits: survivorship in the covered set (why the benchmark is the covered set); text-based scores come from a rough
  parser; filing dates are exact, so there is no lookahead. If the SEC will not serve the filings, this test is not run and is
  reported as not tested.

## Test 2: liquid-ETF reversal (hypothesis 143), `rev5s_h3_band40_etf`
- **Universe:** the 169 ETFs in `research/round16_common.py` (fixed before any result). On a decision date an ETF is **eligible** if
  it has at least 260 sessions of history and a median 60-day dollar volume of at least $20 million. Leveraged, inverse and volatility
  products are excluded by construction.
- **Rule:** every 3 sessions rank eligible ETFs by -(5-day return) / (60-day standard deviation of daily returns x sqrt(5)), hold
  the top 10% with the keep-while-top-40% band, equal weight, signal and fill at the close, **2 bps** (stress 5 bps, the stock
  cost). Benchmark: equal-weight of the eligible ETFs, rebalanced monthly, same costs.
- Report only: unscaled 5-day return; 1-day and 10-day horizons; equity ETFs only; the result at 5 and 10 bps.
- **Survivorship caveat fixed in advance:** the list is of ETFs alive today. Closed ETFs are missing, and a reversal rule that buys
  losers benefits most from that. Even if the rule passes, it is "supported with this caveat" and would need a list of ETFs live at
  each date before any paper order.

## Test 3: statistical peers (hypothesis 144), `peerlag_h3_band40_s`
- **Peers:** on each decision date, for every ranked member, the five members with the highest correlation of daily returns over
  the previous 250 sessions (ending the session before the decision date, at least 200 common days), after subtracting each day's
  equal-weight mean return. Peers come from the evaluated panel's point-in-time members.
- **Signal:** mean 5-day return of the five peers minus the stock's own 5-day return (own return read at the same price as
  the parent). Rule as the parent `rev5_h3_band40_s`: every 3 sessions, top 10%, 40% band, equal weight, 5 bps.
- **Evaluation as round 15:** the full 719-name panel at the close, the 419 names outside the intraday snapshot sample, and the
  300-name snapshot sample at the 15:45 price (peers drawn within each panel; 15:30 price check at 5 bps). Every cell must pass the
  bar (net active >= 2.0%, IR >= 0.3, placebo >= 0.95, 10 bps above 0) **and beat the unfiltered parent run in the same panel**.
- Report only: peers-only signal (without the stock's own return).

## Multiple testing
Three rules, one hypothesis each. A pass can still be luck with 144 tests behind us, so a pass is a lead for a second era
(Sharadar), not a new shadow rule by itself.

## Results (run 2026-10-17)

**Verdict: 0 of 3 supported. Test 1 (142), test 2 (143) and test 3 (144) all rejected.** Nothing is added to the shadow or paper records.
Hypotheses tested after this round: 144. (The SEC refuses requests without a contact email; Garret agreed to use his, kept in the environment
and not stored in the repo.)

### Test 2: liquid-ETF reversal (143), rejected
169 ETFs downloaded (bars start 2016-01-04, so the first ETFs become eligible around January 2017); median 124 eligible on a decision day,
`backtests/round16_etf/`. Net active vs the equal-weight eligible ETFs, per year, 2 bps unless stated.

| Variant | Window | Net active | IR | Placebo | At 5 bps | At 10 bps | Decisions |
|---|---|---|---|---|---|---|---|
| **143 scaled 5-day, 3 sessions (the test)** | IS | +3.2% | 0.30 | 0.99 | +1.1% | -2.3% | 503 |
| | OOS | -1.8% | -0.21 | 0.39 | -3.9% | -7.3% | 317 |
| report: raw 5-day return | IS / OOS | -3.6% / +2.8% | -0.28 / 0.25 | 0.11 / 0.95 | | | |
| report: equities only | IS / OOS | +4.7% / +0.2% | 0.41 / 0.03 | 1.00 / 0.73 | | | |
| report: 1-day, every session | IS / OOS | -4.2% / +0.3% | | | | | |
| report: scaled 10-day, 3 sessions | IS / OOS | +2.1% / +4.4% | 0.20 / 0.49 | 0.93 / 0.99 | +0.8% / +3.1% | -1.3% / +0.9% | |

Plain English: the rule made money in 2017 to 2022 (a bit over 3% a year, and above random picks) and then lost money from 2023 on, so it fails the
both-periods bar. Even in the good period the edge is thin: it turns over about 70 times a year, and 5 bps of cost takes away two thirds of it.
Cheap ETF trading did not rescue reversal. Post-hoc, not pre-registered: the 10-day version of the same idea looks better since 2023 (+4.4%, positive at 5 bps) and
weaker before; with 144 tests behind us it is a lead only. The ETF list is also of funds alive today, which flatters a rule that buys losers, so even a pass would have needed that caveat.

### Test 3: statistical peers (144), rejected
Same three evaluations as round 15; `backtests/round16_peers/`. Net active per year at 5 bps (IS / OOS):

| Panel | Peer-lag rule | Parent (plain reversal) | Peers-only signal (report) |
|---|---|---|---|
| All 719 names, close | +2.2% / -1.7% | +6.2% / +0.3% | -7.6% / +0.7% |
| 419 unseen names | +2.2% / +1.5% | +5.2% / -0.8% | -5.2% / -1.3% |
| 300-name snapshot, 15:45 | +3.6% / -1.5% | +9.9% / +3.0% | -5.3% / +0.6% |

Plain English: asking whether a stock lagged its five most similar stocks last week adds nothing. It does worse than plain reversal in 5 of 6 cells (it
beats the parent only on the unseen names since 2023, where the parent itself lost) and fails the bar everywhere. The peers' own move on its own
predicts nothing (negative in 2017 to 2022); the reversal in the rule comes from the stock's own return.

### Test 1: filing-language change (142), rejected
22,230 10-K and 10-Q filings for all 503 current members downloaded (22,223 usable, 20,198 with a year-earlier match; 7 failed or too short),
`backtests/round16_filings/`. About 406 names are scored on a typical month end. Net active vs the equal-weight scored names, per year.

| Rule | Window | Net active | IR | Placebo | At 10 bps | Rebalances | Turnover/yr |
|---|---|---|---|---|---|---|---|
| **142 20% most similar (cosine)** | IS | +0.2% | 0.04 | 0.65 | -0.1% | 72 | 6.3 |
| | OOS | -0.2% | -0.05 | 0.53 | -0.4% | 45 | 5.9 |
| report: Jaccard similarity | IS / OOS | -0.7% / -0.1% | -0.16 / -0.03 | 0.32 / 0.57 | | | |
| report: 10-K only (about 39 names scored a month) | IS / OOS | -1.5% / -3.2% | -0.23 / -0.39 | 0.00 / 0.00 | | | |
| report: 20% **least** similar | IS / OOS | -0.4% / +2.5% | -0.11 / 0.69 | 0.46 / 0.98 | | | |

Plain English: the companies that rewrote their reports least did no better than the average company in either period, so the published
"stable wording wins" pattern is not here for large US companies since 2017. Costs are not the problem (the rule trades only about 6 times a year); the
signal simply has nothing in it. The least-similar group did well since 2023 (+2.5%, the opposite direction to the paper) but not before; that was not
pre-registered and is a lead only. Limits: covered names are current members, which is why the benchmark is the covered set; the text parser is rough
(word counts, tables dropped), so a better parser could in principle find something this one misses.

## Round summary
All three outside-the-box ideas fail. The two things tried against costs (rare trading, cheap trading) did not produce an edge on their own, and a
signal from relationships between stocks added nothing to plain reversal. Post-hoc leads, none pre-registered and all needing a second era before they mean
anything: the 10-day version of ETF reversal since 2023, and the least-similar filings since 2023.
