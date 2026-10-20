# Round 22: volatility term structure, vol-of-vol and short-term stress as scalers and a timing signal (2026-10-20)

Standing order from Garret (2026-10-20): keep testing new methods round after round until one passes. Ideas chosen by the thread.
Hypotheses 164-167; 163 were tested before this round. Bar unchanged from rounds 6-21; nothing loosened.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
- The only market-state variable used so far is the VIX level (round 12: `vixscale` passes as a steadier, lower-earning version of the reversal rule; `vixgate` fails). Cboe publishes free daily histories that were never used here: VIX3M (since 2009), VIX9D (2011), VVIX (2006). The Cboe CDN is reachable from the cloud container (it redirects; FRED and BLS are not reachable).
- **Term-structure inversion** (VIX above VIX3M) marks acute stress; it is a better-known predictor of near-term equity returns than the VIX level (e.g. Simon-Campasano 2014, "The VIX futures basis"; Cboe's own VIX/VIX3M ratio). Short-term reversal profits are a compensation for liquidity provision and are known to rise in stress (Nagel 2012, "Evaporating Liquidity"), so a stress scaler that reacts faster than the VIX level is a natural refinement.
- **VVIX** (volatility of VIX) measures how unstable the volatility itself is: a different stress dimension from the level.
- **VIX9D / VIX** is the very short end of the curve (inversion within days).
- A pure timing use of the same inversion signal on the market has not been tried either (rounds 2-3 used price-only volatility and trend states).

## Common setup
Daily tests (164-166) use the round 12 construction exactly (`strategies/short_horizon_v5.py`): rule `rev5_h3_band40_s` (top 10% by 5-session reversal, every 3rd session from 2016-12-30, keep a held name while it is in the top 40%), the active share `s = clip(x / median - 0.5, 0, 1)` in the band book and the rest in the equal-weight of all priced members, where x is the **previous session's** close of the state variable and the median is that of the previous 252 closes. Only the state variable changes. Fills at the close, 5 bps (10 bps stress), 2020-03-09..20 excluded as in earlier rounds. Screens: all point-in-time members and members outside the intraday sample ("unseen"), daily-close prices; 15:45 snapshot data is not rebuilt in this round, so a rule that clears the screens would still need the snapshot stage before it counts as a pass.
- **Bar, required in both windows (IS 2017-2022, OOS 2023 on):** net active >= 2.0%/yr vs the benchmark (monthly rebalanced equal-weight members), information ratio >= 0.3, selection placebo >= 0.95 (the band book's picks versus 1,000 random same-size baskets, as in earlier daily rounds), net active > 0 at 10 bps, at least 160 / 100 decisions.
- Because these are branches off the passing `vixscale` rule, a candidate must also **beat both the plain reversal parent and the VIX-level `vixscale` rule (rebuilt here from Cboe VIX closes) in net active** in both windows on both screens.

## Tests
- **164 `rev5_vts_scale`**: x = VIX / VIX3M (inversion above 1).
- **165 `rev5_vvix_scale`**: x = VVIX.
- **166 `rev5_vx9_scale`**: x = VIX9D / VIX.
- **167 `vts_timing_vti`**: a market-timing rule. Hold VTI when the previous session's VIX / VIX3M close is below 1, otherwise BIL; decisions every session close; benchmark buy-and-hold VTI; 5 bps per unit traded (10 bps stress). Bar as above with minimum 48 / 36 months of data (the windows' trading days), placebo = the actual mean daily active return against 1,000 circular shifts of the same in/out series (keeps the lengths of in and out periods). Signal history starts 2009-09; evaluation windows are IS 2016-01-01..2022-12-31 and OOS 2023-01-01 on.

## Multiple testing
Four rules, pre-specified, no variants. A pass would be a candidate for the shadow record only with Garret's say-so.

## Results (run 2026-10-20)

**Verdict: all four rejected (hypotheses 164-167).** Nothing is added to the shadow or paper records. Hypotheses tested after this round: 167.
`backtests/round22_tests/`. Daily-close screens only; no rule cleared them, so no snapshot stage.

Net active per year at 5 bps (all members screen; the unseen-members screen agrees): IS = 2017-2022, OOS = 2023 on.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| Plain band reversal (parent, decisions from 2016-12-30) | +7.0% (IR 0.55) | +3.5% (0.28) | reference |
| VIX-level scaler (`vixscale` rebuilt from Cboe) | +7.1% (0.69) | +2.5% (0.29) | reference |
| **164** VIX/VIX3M scaler | +4.4% (0.57) | +1.7% (0.22) | rejected: below both references, OOS under 2% |
| **165** VVIX scaler | +5.6% (0.64) | +2.0% (0.26) | rejected: IR 0.26 and 10 bps -0.2% in OOS, below both references |
| **166** VIX9D/VIX scaler | +4.6% (0.59) | +1.1% (0.15) | rejected |
| **167** VTI only when VIX/VIX3M < 1, else BIL | -5.8% (-0.44, placebo 0.03) | -4.6% (-0.57, 0.03) | rejected: out of the market 5-9% of days and lost every time (rebounds come right after the inversions) |

### Side finding: the band reversal rule depends on which day the 3-session cycle starts (report only, `research/round22_phase.py`)
The rule decides every 3rd session, so there are three possible phases. Same rule, same data, same costs, net active per year:

| First decision | IS 5 bps | OOS 5 bps | IS 10 bps | OOS 10 bps |
|---|---|---|---|---|
| 2016-12-30 | +7.0% | +3.5% | +3.6% | +0.1% |
| 2017-01-03 | +5.9% | -0.1% | +2.5% | -3.4% |
| 2017-01-04 | +8.9% | +1.8% | +5.5% | -1.7% |

The 2023-on result moves by about 3.6 points just from the starting phase, and the average of the three (+1.7% at 5 bps, about -1.7% at 10 bps) is below the 2.0% bar. So the recent reversal edge on this daily-close screen is within the noise created by the 3-session phase, and thin net of costs; the 15:45 prices used in the shadow record are a different measurement and are not rebuilt here. Worth knowing for the live book (the shadow record is on one phase); not a verdict on its own.

### Plain English
- **Three new stress gauges** (curve inversion, vol of vol, very-short-term stress) used to scale the reversal rule all did worse than the existing VIX-level version, which itself is steadier but earns slightly less than the plain rule.
- **Selling stocks when volatility futures invert** lost about 5% a year: markets usually bounce right after those scares, so being out costs more than it saves.
- **Side finding for the live book:** the reversal rule's 2023-on result swings by several points depending only on which day its every-third-session cycle starts. Averaged over the three starts it is about +1.7% a year at 5 bps and roughly breakeven or negative at 10 bps on this screen. The edge is real in 2017-2022 but thin recently.
