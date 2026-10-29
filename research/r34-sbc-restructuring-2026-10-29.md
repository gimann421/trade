# Round 34: stock compensation, restructuring charges and combined intangible spending (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 209-211; 208 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
The two independent passes are an earnings-quality signal (accruals) and an intangible-investment signal (R&D). Three more from the same two families, each fixed in direction before running:
- **Stock-based compensation over assets, highest quintile** (Kothari-Li-Short, and Aboody-Hughes-Liu on equity pay and performance): a second form of intangible/human-capital investment that is partly expensed and partly not. Direction: highest.
- **Restructuring charges over assets, lowest quintile** (Elliott-Hanna 1996 "repeated accounting write-offs"; Bens-Johnston 2009): firms with repeated charges are lower quality earnings; direction: lowest charge intensity, scored only if the firm reports the tag in any year (no tag = unscored, not zero, because absence of a tag can mean no charge or no disclosure).
- **R&D plus stock-based compensation over assets, highest quintile**: a branch off the proven R&D rule that adds the second intangible-investment form; scored for names with an R&D value (stock compensation counted as zero if the tag is missing for that year).

## Common setup
Round 25-33 setup exactly (annual first-filed 10-K values usable after the filing date, fiscal year within 455 days, current S&P 500 members, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names).
- 209 `sbc_quintile`: highest ShareBasedCompensation / assets (positive values only).
- 210 `lowrestructuring_quintile`: lowest RestructuringCharges / assets among names with the tag in any year (zero where absent that year).
- 211 `rnd_sbc_quintile`: highest (R&D + stock compensation) / assets among names with R&D.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. 211 is a branch off the R&D rule, so it also needs an information ratio above the R&D quintile's on the same names in both windows. Reported, not judged: mirrors; correlation with low accruals and with R&D intensity (above 0.7 means the same bet, not a new rule); tech/health share of the picks.

## Multiple testing
Three rules, no variants. Total tested after this round: 211.

## Results (run 2026-10-29)

**Verdict: `sbc_quintile` (hypothesis 209) clears the numeric bar, but its monthly active return correlates 0.82 with R&D intensity (above the pre-registered 0.7), so it is the same bet and NOT counted as a new rule. 210 and 211 are rejected.** Tests after this round: 211. `backtests/round34_tests/`. Check: the low-accruals and R&D references reproduce.

Net active per year at 5 bps (IR, placebo); IS = 2017-22, OOS = 2023 on:

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| **209 highest stock compensation / assets** | **+3.9% (0.39, 1.00)** | **+9.1% (0.83, 1.00)** | clears the bar; same bet as R&D (corr 0.82) |
| 210 lowest restructuring charges / assets | +2.7% (0.63, 0.98) | -3.4% (-0.77, 0.05) | rejected: reversed since 2023 |
| 211 R&D plus stock compensation / assets | +5.5% (0.52, 1.00) | +14.3% (1.32, 1.00) | rejected: not above the R&D quintile's information ratio (0.52 / 1.43) |

Mirrors (report only): lowest stock compensation -2.5% / -2.5%; highest restructuring +0.6% / -2.9%; lowest R&D plus stock compensation -2.3% / -7.4%. Correlation with low accruals: 0.39, 0.00, 0.37. Correlation with R&D intensity: 0.82, 0.21, 0.92. Mean tech/health share of picks: 78%, 52%, 99%.

### Plain English
- **Companies that pay a lot of their staff in stock** beat the average of that group in both periods (+3.9%/yr, then +9.1%/yr). They are largely the same technology companies as the R&D rule (correlation 0.82), so it is the same bet seen from another angle, not a third independent rule.
- **Adding stock pay to the R&D measure** gave no improvement over R&D alone.
- **Low restructuring charges** worked in 2017-22 and reversed since 2023.
- Still two independent rules: low accruals and R&D intensity. Cash holdings and stock compensation both turn out to be tech-company intangible-investment variants of the R&D rule.
