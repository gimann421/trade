# Round 46: headline content categories (2026-10-29)

Garret's standing ask (keep searching until more rules pass; relayed by the coordinator 2026-10-29). Ideas chosen by the thread. Hypotheses 238-239; 237 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.** Two things were checked beforehand, and only on headline text, never on returns: how many headlines match each pattern for six sample tickers, and which earnings headline formats exist. The pattern for rule 239 was widened once because the first version caught only about 6 earnings headlines per ticker over ten years while about 35 exist.

## Where the ideas come from
Round 42 used only headline counts and a negative-word list. The feed (Alpaca/Benzinga, round 42 download) carries structured content: analyst actions ("Upgrades", "Initiates Coverage", "Price Target") and reported-earnings headlines that state the surprise ("Q2 EPS $0.65 Beats $0.64 Estimate", "Reports Q4 EPS $0.59 vs. Est. $0.52"). Both are read strictly before the decision day.
- **238 `fewanalyst_quintile`, neglect by analysts** (Hong-Lim-Stein 2000, "Bad news travels slowly": information diffuses slowly for low-coverage stocks): the 20% of names with the fewest analyst-action headlines (any of: upgrade, upgrades, downgrade, downgrades, initiates, initiated, price target, maintains, reiterates, reiterated, outperform, overweight, buy rating) in the trailing 180 days. Direction: fewest. Counts are not size-adjusted.
- **239 `epsbeats_quintile`, reported earnings surprise from headlines** (Bernard-Thomas 1989 post-earnings-announcement drift, with the surprise read from the headline instead of a database): among names with at least 3 reported-EPS-versus-estimate headlines in the trailing 365 days, the 20% with the highest count of beats minus misses. A headline is an EPS beat if the reported number is above the estimate in "EPS $a vs. [Est.] $b" form or the text says "EPS $a Beats"; a miss if below or "Misses". Headlines containing sees, raises, lowers, reaffirms, outlook or guidance are ignored (guidance, not a result). Direction: highest net beats. Ties are common (most firms beat most quarters); ties are broken by the engine's ordering, which is alphabetical, and this is a known weakness of the rule.

A name needs at least 20 headlines in the whole file to be scored.

## Common setup
Round 25-45 setup exactly: current S&P 500 members at each date, monthly decisions from 2017-01-31, top 20% of scored names equal weight, benchmark equal-weight scored names, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with low accruals, R&D intensity and sales/price (above 0.7 means the same bet, not a new rule); tech/health share of picks.

## Multiple testing
Two rules, no variants. Total tested after this round: 239.

## Results (run 2026-10-29)

**Verdict: both rejected (hypotheses 238-239).** Tests after this round: 239. `backtests/round46_tests/`. Check: the low-accruals, R&D and sales/price references reproduce. Coverage: 499 to 504 scored names for 238; for 239 only 8 names had three or more earnings-comparison headlines in the first month (so 2017 starts late), 371 to 450 from 2018.

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 238 fewest analyst-action headlines | -0.8% (-0.21, 0.30) | -2.4% (-0.61, 0.08) | rejected: wrong sign in both windows |
| 239 highest net EPS beats | +0.7% (0.19, 0.81) | -0.3% (-0.09, 0.47) | rejected |

Mirrors (report only): most analyst actions +1.4% / +5.5% (placebo 0.93 / 1.00; heavily analyst-covered names won since 2023, the same large-name strength seen in round 42); most net EPS misses -0.7% / -2.0%. Correlation of 238 with low accruals -0.46, R&D -0.31, sales/price 0.05; of 239 with low accruals 0.12, R&D 0.24, sales/price -0.22.

### Plain English
- **Companies analysts barely cover** did worse than average in both periods, the opposite of the neglected-firm theory. **Companies that kept beating earnings estimates** did not outperform either; being a serial beater is already known to the market.
- Still three rules that passed: low accruals, R&D intensity, and (weaker) sales/price.
