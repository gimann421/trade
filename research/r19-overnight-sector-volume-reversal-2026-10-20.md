# Round 19: overnight momentum, sector-adjusted residual momentum, volume attention, and three new reversal rankings (2026-10-20)

Garret asked on 2026-10-20 to keep testing new methods, round after round, until one passes, without asking between rounds. This round's ideas were chosen by the thread (no pick step).
Hypotheses 152-157; 151 were tested before this round. The testing-until-something-passes setup raises the chance of a lucky false pass, so the bar below is the same as in rounds 6-18 and nothing is loosened; the true count of tests is carried into every later round.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
- **Overnight momentum** (Lou, Polk, Skouras, "A Tug of War: Overnight Versus Intraday Expected Returns", JFE 2019): the momentum premium is earned overnight and is partly reversed during the day; stronger in large caps and high-priced stocks. Ranking on the overnight part only has not been tried here (rounds 3-5 tested overnight on index ETFs only, hypotheses 26-27, 79-81, 88). This is a novel branch off the proven momentum family.
- **Sector-adjusted residual momentum** (Moskowitz-Grinblatt 1999 industry-adjusted momentum; Blitz-Huij-Martens 2011 residual momentum): the shadow rule strips out market, size and value only. Stripping out sector moves as well is a branch off the proven rule; the SIC-based industry tests (150) failed, but this uses sector ETF returns, which cover every member including departed ones.
- **Volume-trend attention** (Gervais-Kaniel-Mingelgrin 2001 "high-volume return premium"; Lee-Swaminathan 2000 momentum and volume): momentum names with rising trading volume are the ones attracting attention. Untested here (round 12 skipped only "high-volume" reversal days).
- **Volatility-scaled reversal, close-location reversal, single-jump reversal**: three alternative rankings for the proven 3-session band reversal rule. Residual (rev5r), ex-overnight (rev5n, rev5x), peers (peerlag), volume (rev5v) rankings are already rejected; these three are different (they change what counts as an overreaction: size relative to the stock's own noise, where the day closed in its range, one big day versus a drift).

## Common setup
- Monthly tests (152-154): the round 18 setup. Decisions at month-end closes from 2017-01-31, filled at that close, held to the next decision (`round18_tests.run_rule`). Benchmark equal-weight priced point-in-time S&P 500 members. Windows IS 2016-01-01 to 2022-12-31, OOS 2023-01-01 on; minimum 48 / 36 rebalances. Costs 5 bps (primary), 10 bps (stress).
- Daily tests (155-157): the round 15 setup. Rule `rev5_h3_band40_s` (top 10% S&P 500 names by score, decision every 3 sessions, 40% band), signal and fill at the close, 5 bps primary / 10 bps stress, 2020-03-09 to 2020-03-20 excluded as in earlier rounds, decisions from 2017-01-03, minimum 160 / 100 decisions.
- **Bar, required in both windows:** net active >= 2.0%/yr vs the benchmark, information ratio >= 0.3, selection placebo >= 0.95 (1,000 random same-size baskets, seed 0), net active > 0 at 10 bps.
- Because each is a branch off a proven rule, a pass also needs to **beat the parent** in both windows (monthly 153 and 154: information ratio above the parent's; 155-157: net active above the parent's, as in round 15). 152 is a different signal, so the bar alone applies; its parent is reported.
- Daily tests are screened on two sets: all point-in-time members, and the members outside the 300-name intraday sample ("unseen"). A rule that survives both screens would then be re-run on the 15:45 snapshot data (and the 15:30 noisy signal, which must also stay above 0); only after that is it a pass. Nothing passes on the daily screen alone.
- The round 17 rule applies: a lead that only shows up post hoc cannot be confirmed in the window where it was found; check neighbouring parameters first.

## Test 1 (hypothesis 152): `onmom6_1_decile`, overnight momentum
- Overnight return for a session: open / previous close - 1 (adjusted bars). Score: sum of log(1 + overnight return) over the sessions t-126..t-21 (the 6-1 window), at least 105 valid, an overnight return beyond +-50% treated as missing.
- Hold the top 10% of scored priced members, equal weight.
- Reported only: the bottom decile, and the same window using the intraday part (close / open) top decile; the residual momentum decile as the reference parent.

## Test 2 (hypothesis 153): `resmom_sector_decile`, residual momentum net of sector moves
- The shadow rule's 6-1 residual momentum, but the regression factors are MKT, SMB, HML (as the shadow rule) plus nine sector spreads (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY return minus VTI return).
- Hold the top 10%; benchmark equal-weight priced members.
- **Pass:** the bar in both windows and an information ratio above the shadow parent's in both windows.

## Test 3 (hypothesis 154): `resmom_volrise_decile`, residual momentum with rising volume
- Volume ratio: mean daily volume over the last 63 sessions / mean over the last 252 sessions (needs 200 valid sessions).
- Among names with both a residual momentum score and a volume ratio, keep those with a ratio at or above the median; hold the top 20% of those by residual momentum (about 10% of ranked names).
- Parent in the same run: top 10% by residual momentum among the same names; benchmark equal-weight names with both.
- Report only: the below-median-ratio mirror.
- **Pass:** the bar in both windows and net active above the same-set parent's in both.

## Test 4 (hypothesis 155): `rev5z_h3_band40_s`, volatility-scaled reversal
- Score: minus the 5-session return divided by (the 60-session standard deviation of daily returns times the square root of 5), at the decision close.

## Test 5 (hypothesis 156): `rev5ibs_h3_band40_s`, reversal plus a weak close
- Score: the average of the cross-sectional percentile ranks of (minus the 5-session return) and (minus the day's close location, (close - low) / (high - low)): names that fell over the week and closed near the day's low.
- Note: the decision-day low is known at decision time only approximately at 15:45; the snapshot stage tests that.

## Test 6 (hypothesis 157): `rev5jump_h3_band40_s`, reversal of the biggest single day
- Score: minus the return of the session with the largest absolute return among the last 5 sessions (the jump, not the five-day sum).

## Multiple testing
Six rules, all pre-specified above with no variants. Mirrors are reported, not judged. A pass would be only a candidate for the shadow record, with Garret's say-so; paper orders need his OK as well.

## Results (run 2026-10-20)

**Verdict: all six rejected (hypotheses 152-157).** Nothing is added to the shadow or paper records. Hypotheses tested after this round: 157.
`backtests/round19_tests/`. Check: the shadow parent (residual momentum decile) reproduces its known numbers (IS +4.3%, OOS +8.0%).

Monthly, net active per year at 5 bps (IR, placebo); IS = 2017-2022, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| Parent, residual momentum decile | +4.3% (0.49, 1.00) | +8.0% (0.65, 1.00) | reference |
| **152** top overnight momentum | -0.3% (-0.03, 0.44) | -1.6% (-0.10, 0.18) | rejected: no edge either era |
| mirror: bottom overnight momentum | -1.8% | +1.9% | report only |
| report only: top *intraday* 6-1 return | -1.5% | +6.9% (0.53, 1.00) | one era only |
| **153** residual momentum, sector-adjusted | +0.2% (0.03, 0.75) | +7.3% (0.89, 1.00) | rejected: nothing in IS, below parent |
| Parent on names with a volume ratio | +4.2% (0.48, 1.00) | +8.1% (0.65, 1.00) | reference for 154 |
| **154** residual momentum with rising volume | +3.0% (0.41, 0.99) | +3.3% (0.33, 0.96) | rejected: clears the bar but far below its parent |
| mirror: falling volume | +3.9% | +2.0% | report only |

Daily 3-session band reversal on the daily-close screen (all members / members outside the intraday sample), net active at 5 bps:

| Rule | IS all / unseen | OOS all / unseen | Verdict |
|---|---|---|---|
| Parent rev5_h3_band40_s | +6.2% / +5.2% | -0.1% / -1.2% | reference |
| **155** volatility-scaled reversal | +4.9% / +4.2% | -4.3% / -5.7% | rejected |
| **156** reversal plus weak close | +6.6% / +2.8% | -3.1% / +1.0% | rejected |
| **157** reversal of the biggest day | +1.7% / +1.8% | +0.4% / +2.8% | rejected |

No daily rule cleared both screens, so the 15:45 snapshot stage was not run.
Note: on this daily-close screen the parent itself earns about nothing from 2023 on (the shadow rule's recent gain shows up with the 15:45 prices), so the screen cannot confirm a daily branch in the recent era; none of these three even matched the parent in IS or OOS, so the verdicts do not depend on that.

### Plain English
- **Overnight momentum** (stocks that rose most between the close and the next open): earned nothing. The idea from the academic paper does not show up in large US stocks here.
- **Sector-adjusted momentum:** stripping out sector moves as well removed the 2017-2022 edge entirely. Most of what makes the shadow momentum rule work then is sector-level, not stock-level.
- **Momentum with rising volume:** a real but weaker version of the parent; picking only stocks whose trading is picking up gave up about half the parent's gain.
- **Three new ways to pick reversal candidates:** all did worse than the plain rule.
- Side hint (not a lead; found after the fact, so it cannot be confirmed in this window): stocks with the best *intraday* gains over six months did well since 2023 (+6.9%) but lost in 2017-2022.
