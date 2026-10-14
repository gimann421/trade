> **STATUS: DRAFT, NOT IN FORCE (2026-10-14).** The owner has asked to hold off on stopping rules. Everything below is a proposal, not a commitment: no checkpoint, retirement threshold or "the rule never changes" clause binds anyone yet, and the ledger notes that pointed here are superseded by a note saying the same. The shadow record itself continues; it only records picks. This file will be rewritten and re-committed, before the first forward decision on 2026-10-30, if and when rules are chosen.

# Forward tracking rules for the two supported rules (DRAFT)

- **Date:** 2026-10-13
- **Applies to:** `stock_resmom6_1_decile` (hypothesis 54, primary) and `stock_resmom6_1_quintile` (hypothesis 55, secondary), as tracked by `core/paper_runner.py` from `paper/tracked.json`.
- **Why now:** the first forward decision is 2026-10-30. These rules are written and committed before it, so the checkpoints cannot be bent to fit what the record shows.

## What the record is
- Shadow portfolio started at the 2026-10-30 close with $100,000, 5 bps costs, against an equal-weight portfolio of the same point-in-time S&P 500 members. A rule's **cumulative excess** is its NAV divided by the benchmark NAV, minus 1 (`excess_return` in `paper/<rule>/status.json`).
- A decision counts as forward only if its `decisions/<date>.json` was committed to git no later than the next trading day. A decision committed later is marked late and does not count; each late decision moves both checkpoints back by one month.
- What the record can and cannot show: the excess return is noisy. From the backtest, tracking error is about 9% a year (2017-2022) to 12% (2023 onward). After 24 months the uncertainty on cumulative excess is therefore about 13-17 percentage points. A real edge of 4-8% a year, which is what the backtest showed, produces a negative 24-month result roughly one time in five to one in four; a rule with no edge produces a positive one about half the time. The checks below filter out failures; they do not prove the rule.

## Checkpoints
| When | Check | If it fails |
|---|---|---|
| After the 2027-04-30 close (6 holding months) | **Record check, no performance verdict.** All 6 month-end decision files exist and were committed on time; `decisions_changed_since_recorded` is empty or each entry is explained; `nav.csv` has no gaps. If paper orders have been placed: the average gap between each fill and the decision-day close is under 30 bps. | Fix the runner or the schedule. The rule is not judged. |
| Any month-end after 2027-04-30 | **Disaster stop.** Cumulative excess below -20%. | Retire the rule (status `retired`). That is about two standard deviations of one year of tracking error. |
| After the 2028-10-31 close (24 holding months) | **Direction check.** Cumulative excess below 0. | Retire the rule. |
| After the 2028-10-31 close | Cumulative excess at or above 0. | Keep tracking. This is not proof. Using real money is a separate decision that also weighs the backtest (70 hypotheses tested), any older-history test, and these results. |

## What may and may not change while tracking
- The rule (signal, window, size, rebalance day, costs, benchmark) does not change. A change is a new hypothesis with its own ledger row and its own record starting at its own first decision.
- Runner bug fixes are allowed. A fix that changes any recorded pick must be written up in a note on the hypothesis, with the old and new picks.
- The two rules are judged separately. Passing the quintile does not rescue the decile or the reverse.
- If paper orders start later, they are placed for the decile rule only, at the allocation and risk limits the user sets in `paper/tracked.json` and `config/risk_limits.yaml`. The shadow record continues unchanged either way.
