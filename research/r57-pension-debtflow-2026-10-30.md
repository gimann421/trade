# Round 57: pension funding and net debt issuance (2026-10-30)

Garret's standing ask (keep searching until more rules pass; coordinator re-relayed 2026-10-30, do not pause). Idea chosen by the thread. Hypotheses 262-263; 261 were tested before this round, so a lucky pass is more likely than for a single test. Bar unchanged from round 25.

**This section is written before any result of this test was computed.** Only the XBRL concept list used in rounds 25-56 was looked at.

## Where the idea comes from
Two items not used before. (1) The funded status of defined benefit pension plans over assets: an underfunded plan is a hidden debt, and the market may under-react to it. (2) Net debt issuance over the last fiscal year (long-term debt proceeds minus repayments) over assets: a financing-side flow, distinct from the share-issuance (round 39) and buyback (round 49) tests. Directions pre-registered: 262 high funded status = buy; 263 lowest net debt issuance (most deleveraging) = buy. Mirrors are reported but not judged.

## Rules (top 20% of scored names, equal weight, benchmark equal-weight scored names)
- 262 `pensionfunded_quintile`: `DefinedBenefitPlanFundedStatusOfPlan` at the latest fiscal year end / assets. Names with no such fact are not scored. Highest 20%.
- 263 `lowdebtissuance_quintile`: (`ProceedsFromIssuanceOfLongTermDebt` minus `RepaymentsOfLongTermDebt`, 350-380 day flows, missing leg counts 0, at least one leg present) / assets. Lowest 20%.
Annual data: latest 10-K filed before the decision, no older than 455 days.

## Common setup
Round 25-56 setup exactly: current S&P 500 members, monthly decisions from 2017-01-31, 5/10 bps, IS 2017-22, OOS 2023+, minimum 20 scored names.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors; correlation with the three passes; tech/health share. Correlation above 0.7 with an existing pass is the same bet.

## Multiple testing
Two rules, no variants. Total tested after this round: 263.

## Results (run 2026-10-30)

**Verdict: both rejected (hypotheses 262-263).** Tests after this round: 263. `backtests/round57_tests/`. Reference rules reproduce (low accruals +2.8/+3.2, R&D +5.5/+15.8, sales/price +4.5/+3.3).

| Rule | IS | OOS | Verdict |
|---|---|---|---|
| 262 highest pension funded status / assets | -1.3% (IR -0.21, pl 0.35) | -0.5% (-0.06, pl 0.46) | rejected; only 16-35 scored names, 47 IS rebalances |
| 263 lowest net debt issuance / assets | -1.4% (-0.27, pl 0.21) | -1.8% (-0.37, pl 0.24) | rejected |

Mirror (report only, not judged, found post hoc so it cannot be confirmed in these windows): HIGHEST net debt issuance IS +2.5% (IR 0.42, pl 0.91), OOS +6.1% (IR 1.05, pl 1.00), 10 bps +2.4%/+6.0%. It misses the bar only on the IS placebo (0.91 < 0.95). Correlation with the three passes at most 0.14 in absolute terms for ld, so it would be a new bet if real. It is a lead to retest on fresh data (Sharadar era), not a pass. Pension coverage is too thin (under 40 names a month) to test.

### Plain English
Well-funded pension plans and low borrowing did not help; both did slightly worse than average. The reverse of the borrowing rule (firms that borrowed the most) did better in both periods and nearly cleared the bar, but since we only noticed it after looking, it does not count and needs fresh data to confirm.
