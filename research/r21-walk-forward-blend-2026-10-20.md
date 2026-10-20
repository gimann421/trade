# Round 21: a walk-forward model that blends price and volume signals (2026-10-20)

Standing order from Garret (2026-10-20): keep testing new methods round after round until one passes, without asking between rounds. Ideas chosen by the thread.
Hypotheses 162-163; 161 were tested before this round. The bar is the same as in rounds 6-20; nothing is loosened.

**This section is written before any result of these tests was computed.**

## Idea
Rounds 6-20 tested one signal at a time. A signal that is too weak alone can still help in a blend (Gu-Kelly-Xiu 2020, "Empirical Asset Pricing via Machine Learning", where simple linear and shrunk models capture most of the gain; Freyberger-Neuhierl-Weber 2020 on which characteristics matter). Here a heavily shrunk linear model (ridge) is trained only on data that was known at the time, retrained as time passes, and used to rank the S&P 500 members. This is a new *method*, not a new signal: it can find a combination that single-signal tests missed, and it can adapt when a signal changes sign between eras.
Data limit: Alpaca free daily bars start in 2016-01 (checked: a 2014 request still returns 2016-01-04), so the first model has only about six months of history; the feature look-backs are capped at 126 sessions for that reason.

## Common setup
- Features (all at the decision close, each ranked across the point-in-time S&P 500 members that day and centred to [-0.5, 0.5], missing = 0): the 12 below per model. Missing values are filled with 0 (the median) after ranking.
- Target: the member's forward return over the model's horizon minus the cross-sectional mean, ranked and centred the same way.
- Model: ridge regression with a fixed penalty (solve (X'X/n + 0.05 I) w = X'y/n), no intercept, **no tuning**. Training uses only sample dates whose targets were fully realised by the decision date; samples are spaced by the horizon and pooled over all members and all earlier dates (expanding window). The same fixed penalty is used everywhere; no other settings are tried.
- Score = X w; the rest follows the existing engines.
- **Bar, required in both windows:** net active >= 2.0%/yr, information ratio >= 0.3, selection placebo >= 0.95, net active > 0 at 10 bps. IS 2017-2022, OOS 2023 on; minimum rebalances 48 / 36 (monthly) and decisions 160 / 100 (3-session).
- Because the model chooses its own weights from past data, there is no neighbour set to check; the learned weights by era are reported instead.

## Test 1 (hypothesis 162): `blend_m_quintile`, monthly
- Horizon 21 sessions; monthly decisions at month-end closes from 2017-01-31 (round 18-20 engine), hold the top 20% by score, equal weight; benchmark equal-weight priced members.
- Features: 5-session return, 21-session return, 3-1 and 6-1 month return, 63-session volatility, 63-session beta to VTI, highest daily return of 21 sessions (MAX), 63-session return skewness, volume 21/126 ratio, summed overnight return over t-126..t-21, summed intraday return over t-126..t-21, distance below the 126-session high.
- Reference parents in the same run: the shadow residual momentum decile.
- **Pass:** the bar in both windows. (It is a new method; being above the residual momentum parent is reported, not required.)

## Test 2 (hypothesis 163): `blend_d_band`, 3-session band
- Horizon 3 sessions; decisions every 3 sessions from 2017-01-03; model refit on the first decision day of each month; top 10% with the 40% keep-while-top band (the `rev5_h3_band40_s` selection rule), fills at the close.
- Features: 1-, 2-, 5-, 10- and 21-session returns, 20-session volatility, volume 5/60 ratio, close location in the day's range, today's overnight gap, today's intraday return, distance below the 126-session high, 6-1 month return.
- Screens as in rounds 15 and 19: all point-in-time members and members outside the intraday sample ("unseen"), daily-close fills, 2020-03-09..20 excluded; a rule must clear the bar and beat the plain reversal parent's net active in both windows on both screens before the 15:45 snapshot stage is considered (needed only if it clears the screens).

## Multiple testing
Two models, one fixed penalty, pre-specified, no variants. A pass would be a candidate for the shadow record with Garret's say-so.

## Results (run 2026-10-20)

**Verdict: both rejected (hypotheses 162-163).** Nothing is added to the shadow or paper records. Hypotheses tested after this round: 163.
`backtests/round21_tests/`. The reference parent (residual momentum decile) reproduces its known numbers (IS +4.3%, OOS +8.0%).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| **162** monthly blend, top 20% | -4.9% (IR -0.66, placebo 0.00) | -2.8% (-0.35, 0.02) | rejected: worse than random picks in both eras |
| Parent, residual momentum decile | +4.3% (0.49, 1.00) | +8.0% (0.65, 1.00) | reference |
| **163** 3-session blend, all members / unseen | -4.6% / -5.3% | -5.6% / -6.4% | rejected: placebo 0.00-0.06 |
| Plain reversal parent | +6.2% / +5.2% | -0.1% / -1.2% | reference |

Learned weights (average by era; negative = prefers losers): the monthly model leaned on short-term reversal (21-session return -0.018, 5-session -0.011) and on negative skewness, and the 3-session model leaned on 10- and 21-session reversal (-0.007, -0.012) more than on the 5-session return the proven rule uses. Longer-than-a-week reversal is what the model found in its short training window, and it does not pay in large caps.

### Plain English
A statistical model that blends twelve signals and relearns as time passes did **worse than picking stocks at random**, both for the monthly and the every-three-days versions, in both eras. With only about six months of history to learn from when it starts (free price data begins in 2016), it learns patterns of the 2016 market that then reverse. It is not a bug in the sense of a look-ahead (training only used outcomes known at the time), but it means this method needs far more history than we can get for free; the Sharadar data (1998 on, including delisted names) would be the place to retry it.
