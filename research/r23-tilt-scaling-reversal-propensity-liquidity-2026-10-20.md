# Round 23: volatility-scaled momentum tilt, stock-specific reversal propensity, illiquidity, small dollar volume, January pause (2026-10-20)

Standing order from Garret (2026-10-20): keep testing new methods round after round until one passes. Ideas chosen by the thread.
Hypotheses 168-172; 167 were tested before this round. Bar unchanged from rounds 6-22; nothing loosened.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
- **Volatility-scaled momentum** (Barroso-Santa-Clara 2015, "Momentum has its moments"; Daniel-Moskowitz 2016, "Momentum crashes"): momentum's risk is predictable from its own recent volatility, and scaling down when that is high lifts the risk-adjusted return. Applied here as a *tilt scaler* on the proven residual momentum rule: it never goes to cash, it blends the picks with the equal-weight members.
- **Stock-specific reversal propensity**: some stocks' daily returns are persistently negatively autocorrelated (liquidity-provider driven), others are not. The band reversal rule treats all alike. Untested here: rounds 12-17 conditioned on market state, volume, volatility, 52-week high and trend, never on the stock's own autocorrelation.
- **Illiquidity** (Amihud 2002) and **small dollar volume** (a size proxy within the index): published premia, never tested on the S&P 500 members here.
- **January pause for momentum** (Jegadeesh-Titman 1993): momentum is weak or negative in January. Only a handful of Januarys exist in the windows, so this is a low-power test and is judged the same way.

## Common setup
Monthly tests (168-172) use the round 18-22 engine: decisions at month-end closes from 2017-01-31, fills at that close, benchmark equal-weight priced point-in-time S&P 500 members, IS 2016-01-01..2022-12-31, OOS 2023-01-01 on, at least 48 / 36 rebalances, 5 bps (10 bps stress). The daily test (169) uses the round 22 construction (`strategies/short_horizon_v5.py` band rule, decisions every 3rd session starting 2016-12-30, daily-close screen on all members and on members outside the intraday sample, 2020-03-09..20 excluded).
**Bar, required in both windows:** net active >= 2.0%/yr, information ratio >= 0.3, selection placebo >= 0.95 (1,000 random same-size baskets, seed 0), net active > 0 at 10 bps. Branches off a proven rule must also beat that parent's net active in both windows.
Because the 3-session rule's result depends on its phase (round 22), 169 is judged on the 2016-12-30 phase (the shadow record's phase) and its result on the other two phases is reported; a pass on one phase only would be called borderline.

## Test 1 (hypothesis 168): `resmom_volscaled_tilt`
- Picks: the shadow rule's (top 10% by 6-1 residual momentum). Parent daily active return series (parent minus benchmark, 5 bps) is observed through the decision close.
- Scale s = min(1, median of the previous 126-session active-return standard deviations seen so far / the latest 126-session standard deviation); s = 1 until 252 sessions of parent history exist. Weights: s on the picks (equal weight) and 1 - s on the equal-weight of all priced members.
- Placebo: random same-size baskets from the ranked names with the same s.
- **Pass:** the bar in both windows and information ratio above the parent's in both (a scaler is meant to improve risk-adjusted return, so net active need only meet the bar).

## Test 2 (hypothesis 169): `rev5_acfneg_h3_band40_s`
- Stock-specific propensity: the lag-1 autocorrelation of daily returns over the 126 sessions ending at the decision close (at least 100 valid). Rank the 5-session reversal only among the names with autocorrelation below the cross-sectional median (more mean-reverting names). Mirror (reported only): above the median.
- **Pass:** the bar in both windows on both screens and net active above the plain parent's.

## Test 3 (hypothesis 170): `illiq_high_quintile`
- Amihud ratio: mean over the 126 sessions ending at the decision close of |daily return| / (close x volume) (at least 100 valid). Hold the 20% most illiquid priced members. Mirror: most liquid quintile.

## Test 4 (hypothesis 171): `lowdv_quintile`
- Mean close x volume over the 126 sessions ending at the decision close; hold the 20% with the lowest dollar volume. Mirror: highest.

## Test 5 (hypothesis 172): `resmom_nojan`
- The shadow rule's picks in every month except that for decisions at the end of December (the January holding period) the portfolio is the equal-weight of all priced members instead.
- **Pass:** the bar in both windows and net active above the parent's in both. (Expected to be small: one month in twelve differs.)

## Multiple testing
Five rules, pre-specified, no variants; mirrors reported only. A pass would be a candidate for the shadow record only with Garret's say-so.

## Results (run 2026-10-20)

**Verdict: all five rejected (hypotheses 168-172).** Nothing is added to the shadow or paper records. Hypotheses tested after this round: 172.
`backtests/round23_tests/`. The parent residual momentum decile reproduces its known numbers (IS +4.3%, OOS +8.0%).

Monthly, net active per year at 5 bps (IR, placebo); IS = 2017-2022, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| Parent, residual momentum decile | +4.3% (0.49, 1.00) | +8.0% (0.65, 1.00) | reference |
| **168** volatility-scaled tilt (mean share 0.80) | +3.2% (0.49, 1.00) | +5.1% (0.62, 1.00) | rejected: IR no better than the parent's in IS (equal) and below it in OOS; net active lower |
| **172** momentum paused in January | +4.5% (0.52, 1.00) | +5.8% (0.48, 1.00) | rejected: IS slightly better, OOS well below the parent (January 2023-2026 were good momentum months) |
| **170** most illiquid quintile (Amihud) | -1.6% (-0.19, 0.05) | -2.2% (-0.39, 0.06) | rejected |
| mirror: most liquid quintile | +1.4% | +4.1% (0.76, 1.00) | report only |
| **171** lowest dollar volume quintile | -2.1% (-0.36, 0.01) | -5.0% (-0.98, 0.00) | rejected |
| mirror: highest dollar volume quintile | +1.1% | +6.7% (0.86, 1.00) | report only: large, liquid names win, IS flat |

Daily 3-session reversal, daily-close screens, net active at 5 bps (IS / OOS):

| Rule | all members | unseen members |
|---|---|---|
| Parent, phase 2016-12-30 | +7.0% / +3.5% | +5.1% / +3.1% |
| **169** reversal among more mean-reverting names | +1.2% / +7.0% | +2.0% / +7.2% |
| mirror: less mean-reverting names | +8.6% / -0.1% | +5.5% / +0.0% |

**169 rejected:** the IS result is far below the parent (+1.2% vs +7.0%, IR 0.10, negative at 10 bps). It flips sign by era (strong since 2023, weak before) and the other two phases do not clear either (phase 1: +4.3% / -3.0%; phase 2: +2.3% / +2.4%). The mirror (less mean-reverting names) is the one that carries 2017-2022 and loses since 2023. Same sign-flip story as other rounds.

### Plain English
- **Scaling the momentum rule by its own recent volatility** lowered the profit without improving the risk-adjusted result, so it is not worth the extra complexity.
- **Pausing momentum in January** helped a little before 2023 but cost a lot since 2023, because the recent Januarys were good for momentum.
- **Illiquid or small-turnover stocks** lost in both eras. Since 2023, the large and liquid names (highest dollar volume) have done well, but they were flat in 2017-2022: a one-era pattern again.
- **Reversal among stocks that tend to mean-revert** worked since 2023 but not before; the stocks that do *not* tend to mean-revert carried the earlier years. The two eras disagree, so no edge.
