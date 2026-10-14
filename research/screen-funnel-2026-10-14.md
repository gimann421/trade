# Screen funnel: forward test for three-era passers, luck-count review on top (2026-10-14)

Set up at the user's request. The research bar is unchanged; this only decides what gets followed forward and what gets deeper work.

**Stage 1 (forward test).** Any cell that passes the existing bar (net active ≥ 2%/yr, information ratio ≥ 0.3, placebo ≥ 0.95, or the rule's own kill threshold for single-symbol rules) in all three eras (2016-22, 2023+, 2000-15) gets a forward shadow record. Shadow only: no orders, ever, for this kind of rule.

**Stage 2 (chance it is luck).** `research/three_era_screen.py` computes, for the group of passers, the expected share that are flukes: cells × (pass rate per era multiplied together) divided by the number that passed, capped at 100%. It prints `ALERT` when that is 10% or lower; that is the signal to do the deeper work (neighbouring funds and settings, an economic story, a hard look at the data).

**Today.** 108 cells; pass rates 24% (2016-22), 12% (2023+), 38% (2000-15). Luck alone predicts 1.19 cells passing all three. One does: gap-fade washout on XLK (H28). Expected fluke share: 100%. No alert. The forward record for it is `etf_gapfade_xlk` (start 2026-10-15, `core/signal_tracker.py`); H28 stays rejected in the ledger.

**Limits.** The count covers the 108 cells re-run in the older-era retest (rounds 1-4); the 37-rule scan, the short-horizon round and the earnings round are not in it. Rounds 1 and 2 stored no placebo values, so a per-cell p-value version (Benjamini-Hochberg) is not possible from stored results. The luck count assumes the eras are independent for a rule with no edge. 10% is the level at which to look further, not a pass.
