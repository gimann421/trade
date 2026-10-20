# Round 20: index additions, residual skewness, lottery-day, quiet volume build-up (2026-10-20)

Garret's standing order (2026-10-20): keep testing new methods round after round until one passes, without asking between rounds. This round's ideas were chosen by the thread.
Hypotheses 158-161; 157 were tested before this round. With this many tests, a lucky pass becomes likelier, so the bar is exactly the same as in rounds 6-19 and nothing is loosened; a borderline result will be called borderline.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
- **Recent S&P 500 additions** (Shleifer 1986; Harris-Gurel 1986; later work shows the announcement pop has shrunk and partly reverses): the membership file dates every addition from 1996, which nobody has used here as a signal. Stocks added to the index are bought by index funds around the effective date; the question is what they do over the following months. Novel in this repo.
- **Residual skewness** (Boyer-Mitton-Vorkink 2010; Amaya et al. 2015): stocks with lottery-like return distributions are overpriced; low (negative) skewness stocks earn more. Different from the low-volatility and low-beta tests (58-61), which were rejected.
- **Lottery-day maximum** (Bali-Cakici-Whitelaw 2011, "MAX"): stocks with an extreme best day in the past month have low future returns. Picked-over for the whole market, but untested here and a cheap companion to the skewness rule on the large-cap universe.
- **Quiet volume build-up** (Lee-Swaminathan 2000; Gervais et al.): volume rising without price moving may be quiet accumulation. Not the same as round 19's volume ratio inside momentum (154).

## Common setup
The round 18 / 19 monthly engine: decisions at month-end closes from 2017-01-31, filled at that close, held to the next decision (`round18_tests.run_rule`). Benchmark: equal-weight priced point-in-time S&P 500 members. Windows IS 2016-01-01 to 2022-12-31, OOS 2023-01-01 on; at least 48 / 36 rebalances. Costs 5 bps primary, 10 bps stress.
**Bar, required in both windows:** net active >= 2.0%/yr, information ratio >= 0.3, selection placebo >= 0.95 (1,000 random same-size baskets from the ranked names, seed 0), net active > 0 at 10 bps.
Round 17 rule: a lead found after the fact cannot be confirmed in the same window.

## Test 1 (hypothesis 158): `recent_adds`
- A name is a recent addition on a decision day if it first appears in the membership file on a change date within the previous 126 calendar days and was absent from every membership row in the 365 days before that (cuts ticker renames and re-adds).
- Hold all recent additions with a price that day, equal weight; need at least 5 or no trade (a no-trade month counts as zero active return, as in the round 18 engine).
- Ranked set for the placebo: all priced members.
- Report only: all members except recent additions.

## Test 2 (hypothesis 159): `resskew_low_quintile`
- Residual returns from the shadow rule's regression (constant + MKT, SMB, HML ETF factors) over the sessions t-252..t-21, at least 231 valid sessions; score = sample skewness of the residual returns.
- Hold the 20% of scored priced members with the lowest skewness; report the highest-skewness quintile as the mirror.

## Test 3 (hypothesis 160): `max_low_quintile`
- MAX = the largest daily return in the 21 sessions ending at the decision close (at least 19 valid); hold the 20% of priced members with the lowest MAX. Mirror: highest MAX.

## Test 4 (hypothesis 161): `quietvol_third`
- Volume ratio = mean volume over the last 21 sessions / mean over the last 252 (at least 200 valid). Move = absolute 21-session return.
- Hold names in the top third by volume ratio and the bottom third by move (about 11% of names), equal weight; need at least 5 names or no trade.
- Report only: top third volume ratio and top third move.

## Multiple testing
Four rules, pre-specified, no variants. Mirrors are reported, not judged. A pass would be a candidate for the shadow record only with Garret's say-so.

## Results (run 2026-10-20)

**Verdict: all four rejected (hypotheses 158-161).** Nothing is added to the shadow or paper records. Hypotheses tested after this round: 161.
`backtests/round20_tests/`. Recent additions per decision: median 7 names (1 to 15).

Net active per year at 5 bps (IR, placebo); IS = 2017-2022, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| **158** recent index additions | -6.2% (-0.38, 0.03) | +10.5% (0.51, 0.97) | rejected: sign flips between eras |
| **159** lowest residual skewness | +0.2% (0.05, 0.68) | -2.7% (-0.60, 0.03) | rejected |
| mirror: highest skewness | -0.3% | +3.8% (0.72, 1.00) | report only: one era |
| **160** lowest best-day (MAX) | +0.6% (0.07, 0.93) | -7.6% (-1.05, 0.00) | rejected |
| mirror: highest MAX | +0.3% | +6.9% (0.69, 1.00) | report only: one era |
| **161** high volume ratio, small move | +0.5% (0.08, 0.81) | -2.8% (-0.49, 0.20) | rejected |
| mirror: high volume ratio, big move | +0.0% | +1.4% | report only |

### Plain English
- **New index members** did badly in 2017-2022 (-6% a year vs the average member) and well since 2023 (+10.5%). A rule that flips sign by era is not an edge; with only about 7 names at a time it is also very noisy.
- **Avoiding "lottery" stocks** (low skewness, low best-day) lost since 2023: the market paid the lottery-like stocks instead, which is the opposite of the published pattern. Before 2023 the rules earned about nothing.
- **Quiet volume build-up** earned nothing before 2023 and lost after.
- Hint only (found after the fact in the window, cannot be confirmed there): high-skew and high-MAX names beat since 2023 and were flat before, same sign-flip story as recent additions: since 2023 the market has rewarded speculative stocks.
