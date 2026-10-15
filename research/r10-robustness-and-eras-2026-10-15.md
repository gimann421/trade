# Round 10: is the round-9 pass luck, and does short-term reversal exist across eras? (hypotheses 103-111, plus two era families)

- **Date:** 2026-10-15
- **Plan:** the round-10 research plan shared in the thread on 2026-10-14 (Phase 1 and Phase 3; Phase 2 waits for review)
- **Ledger hypothesis ids:** 103-111, titles "Short-horizon v3: <rule id>" (Phase 1). Phase 3 is report-only evidence on the round-9 hypothesis and is not a ledger test.
- **Strategy file:** `strategies/short_horizon_v3.py` (the round-9 rules with the band, book size and window as parameters); scoring in `research/round10_neighbours.py`; era work in `research/round10_eras.py`.
- **What was known when this was written:** round 9 in full. `rev5_h2_band_s` (5-day reversal, decide every 2 sessions, top 10% of names, keep a held name while in the top 30%) passed on the 300-name sample at 15:45 snapshot timing: net active +6.7% / +6.6%, IR 0.43 / 0.45, placebo 1.00 / 1.00, 10 bps +2.0% / +1.9%, 15:30 signal +5.0% / +6.3%. Its close-timed version on the other 419 members: +4.6% / +4.7%, IR 0.34 / 0.35, 10 bps +0.1% / +0.1%. 102 hypotheses tested. No return of any rule below has been computed.

## Phase 1: neighbours of the passing rule (hypotheses 103-111)
One factor changes at a time from the base (band 30%, hold 2, book 10%, window 5), then two combinations. The base itself is hypothesis 99 (`rev5_h2_band_s`; hypothesis 102 is the last of round 9) and is not re-registered.

| Id | Band | Hold | Book | Window |
|---|---|---|---|---|
| `rev5_h2_band20_s` | 20% | 2 | 10% | 5 |
| `rev5_h2_band40_s` | 40% | 2 | 10% | 5 |
| `rev5_h3_band_s` | 30% | 3 | 10% | 5 |
| `rev5_h2_band_b5_s` | 30% | 2 | 5% | 5 |
| `rev5_h2_band_b15_s` | 30% | 2 | 15% | 5 |
| `rev3_h2_band_s` | 30% | 2 | 10% | 3 |
| `rev7_h2_band_s` | 30% | 2 | 10% | 7 |
| `rev5_h3_band20_s` | 20% | 3 | 10% | 5 |
| `rev5_h3_band40_s` | 40% | 3 | 10% | 5 |

Everything else is as in round 9: point-in-time S&P 500 members, 15:45 price on the decision day with fill at the official close, 5 bps on turnover (10 bps stress), the 15:30-signal check, March 2020 dropped, windows 2017-2022 and 2023 on, the same bar (net active >= 2%, IR >= 0.3, placebo >= 0.95 in each window; positive at 10 bps; positive with the 15:30 signal). Minimum decisions 250 / 150 for hold 2 and 150 / 100 for hold 3.

**Universe.** First the same 300-name sample as round 9 (its snapshots are in hand). Then, once the other 419 members' snapshots are downloaded, the nine neighbours and the base are run again on those 419 alone, and on all 719 together.

### How the family is judged
The family is the base plus nine neighbours (10 cells). It is **supported as a plateau** only if all hold:
1. The base and at least 6 of the 9 neighbours pass the full bar on the 300-name sample.
2. The base passes the full bar on the 419 unseen names (snapshot timing, the real test the close-timed check in round 9 only hinted at).
3. No neighbour that fails does so with net active below -2% in either window (a cliff next to the base would say the base sits on a spike).

If 2 fails, the base is labelled **fragile**: the round-9 pass is kept in the ledger as supported (it met its bar) but with a note, and the shadow record continues unchanged. If 1 fails but 2 passes, the rule is labelled **narrow**. The ledger records a note on hypothesis 99 with the count either way. Nothing here changes the shadow record.

## Phase 3: does reversal exist across eras? (report-only)
Round 9 has no pre-2016 stock evidence. Two families check the mechanism on data that reaches further back. Neither is tradable evidence for the stock rule and neither adds a hypothesis to the ledger; both are reported as context with their numbers, whichever way they come out.

**C1. Ken French 49 industry portfolios (value-weighted, daily), July 1926 to August 2026.** Every 2nd day, hold the top 5 of 49 industries (about 10%) by minus their 5-day return, equal weight, with the same hysteresis (keep a holding while in the top 15 of 49, about 30%). Benchmark: equal weight of all 49, rebalanced at the same dates. Costs 5 bps per unit of turnover (an assumption: the portfolios are not tradable). Eras fixed in advance: 1927-1949, 1950-1974, 1975-1999, 2000-2015, 2016 to the end. Reported per era: gross and net active return, IR, and a placebo of 1,000 random same-size baskets (seed 0). Reversal is called **present in an era** when net active > 0 and placebo >= 0.95 in it; across eras it is **broadly present** if present in at least 4 of 5.

**C2. Nine sector funds (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY), Yahoo daily bars, December 1998 to October 2026.** Every 2nd close, hold the top 3 of 9 by minus their 5-day return, with the keep-while-top-4 rule (one extra slot), equal weight, benchmark equal weight of the nine. Close-timed only (no snapshots exist before 2016), 5 bps. Eras: 1999-2007, 2008-2015, 2016 on. Same reporting and the same "present" test as C1 (all 3 eras for "broadly present"). XLF's false -17.8% day on 2016-09-19 is dropped, as are the 10 sessions in March 2020 for the 2016-on era.

What each outcome would mean: if reversal is broadly present in C1 and C2, the stock result is one instance of a long-lived effect and the fragility risk falls. If it is present only after 2016, the stock result is probably a recent regime and should be watched for decay. If it is absent everywhere except the stock sample, that is evidence against.

## Limits
Stocks only from 2016; the sample is 300 names until the download finishes; flat 5 bps; closing-auction competition not modelled; the 49 industries are value-weighted portfolios, not funds; the era cut-offs were set before looking at any era result.

## Results
(to be filled after the runs)
