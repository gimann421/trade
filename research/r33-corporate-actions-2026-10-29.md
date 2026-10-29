# Round 33: recent splits, spin-off parents and special dividends (2026-10-29)

Garret's standing ask (keep searching until more rules pass) continues. Ideas chosen by the thread. Hypotheses 206-208; 205 were tested before this round, so a lucky pass is more likely than for a single test. The bar is the round 25 bar, unchanged.

**This section is written before any result of these tests was computed.**

## Where the ideas come from
Event-driven ideas from a source not used before in this form: Alpaca corporate-action records (forward splits, spin-offs, cash dividends flagged special), for every S&P 500 member ticker including departed ones. Dividend months and payers were tested in round 24; these events were not.
- **Recent forward splits** (Ikenberry-Lakonishok-Vermaelen 1995 "Market underreaction to open market share repurchases" is the buyback study; the split drift is Ikenberry-Rankine-Stice 1996 "What do stock splits really signal?" and Desai-Jain 1997 long-run split drift): names that split in the past year keep outperforming for 1-3 years.
- **Spin-off parents** (Cusatis-Miles-Woolridge 1993; McConnell-Ovtchinnikov-Sheikh): the parent firm that spun off a unit outperforms afterwards; look-back two years.
- **Special dividends** (Brickley 1983; Michaely-Thaler-Womack 1995 on dividend initiations): firms paying a special cash dividend signal strength; look-back one year.
Limits to state up front: Alpaca gives the ex-date only, so an event is treated as known from its ex-date (later than the announcement: conservative); coverage is current members' tickers plus departed members' tickers; and the event counts are small (expect 8 to 30 names at a time), so the rules will hold cash in months with fewer than 8 names, and low power is a real limit.

## Common setup
Monthly decisions at month-end closes from 2017-01-31, filled at that close, held to the next decision, equal weight, benchmark equal-weight priced point-in-time S&P 500 members (`round18_tests.run_rule`), IS 2017-22 and OOS 2023+, 5 bps primary, 10 bps stress; minimum 48 / 36 invested rebalances as in earlier rounds (an event rule that is mostly in cash fails this minimum and is rejected for low power, which is reported as such).
- 206 `recent_split_basket`: members with a forward split (new rate / old rate >= 1.5) whose ex-date is within the previous 365 days; hold all of them if at least 8, else cash.
- 207 `spinoff_parent_basket`: members that are the source of a spin-off with ex-date within the previous 730 days; at least 8, else cash.
- 208 `special_dividend_basket`: members with a special-flagged cash dividend with ex-date within the previous 365 days; at least 8, else cash.

## Bar, required in both windows
Net active >= 2.0%/yr, IR >= 0.3, placebo >= 0.95 (1000 draws, seed 0), net active > 0 at 10 bps. Reported, not judged: mirrors are not defined for baskets; the average basket size; the tech/health share of the baskets.

## Multiple testing
Three rules, no variants. Total tested after this round: 208.

## Results (run 2026-10-29)

**Verdict: all three rejected (hypotheses 206-208), mainly for low power.** Tests after this round: 208. `backtests/round33_tests/`. Events: 106 forward splits (ratio >= 1.5) and 53 spin-offs in the downloaded record, plus the special-flagged dividends from round 24.

| Rule | Median basket | Months invested (of 117) | IS | OOS | Verdict |
|---|---|---|---|---|---|
| 206 recent forward splits | 7 | 44 | +0.2% (IR 0.03, placebo 0.54), 18 rebalances | +8.8% (IR 0.80, placebo 1.00), 26 rebalances | rejected: nothing in 2017-22, too few invested months |
| 207 spin-off parents | 4 | 40 | -1.1% (IR -0.28), 7 rebalances | +1.5% (IR 0.16), 33 rebalances | rejected |
| 208 special dividends | 5 | 28 | +1.6% (IR 0.42, placebo 0.89), 9 rebalances | +0.6% (IR 0.11), 19 rebalances | rejected |

The event baskets were mostly under the 8-name minimum, so the rules sat in cash most months and the invested months fall below the 48 / 36 rebalance minimums in both windows. The tests cannot show an edge with so few events. The split rule's +8.8% since 2023 is a post-hoc hint only: it is zero in 2017-22 and is partly the 2023-25 splits of AI and tech names (52% tech/health baskets).

### Plain English
- **Companies that recently split their stock, spun off a unit, or paid a one-time special dividend** showed no usable edge. There are too few such events among S&P 500 names to hold a basket most months, and the recent-split gain since 2023 did not exist in 2017-22.
- No new rule. Still two: low accruals and R&D intensity.
