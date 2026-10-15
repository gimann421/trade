# Round 13: novel short-horizon ideas from the deep-research report (hypotheses 126-133)

- **Date:** 2026-10-15
- **Source:** `research/deep-research-novel-short-horizon-ideas-2026-10-15.md` (also in `/mnt/project-files/research/`). Garret said "Yeah let's test all" on the ranked report of 10 ideas.
- **Ledger hypothesis ids:** 126-133, one per rule, titles "Novel ideas: <rule id>". 125 tested before this round (the Short horizon methods thread owns the ledger count); 133 after.
- **Files (written after this memo is committed):** `strategies/short_horizon_v6.py`, `research/round13_data.py`, `research/round13_filters.py`, `research/round13_events.py`, `research/round13_weekday.py`.
- **What was known:** rounds 1-12. The parent is `rev5_h3_band40_s` (supported on all 718 names and the 418 unseen). No return of any rule below has been computed when this memo is committed. The only things looked at beforehand: that each data source can be downloaded (FINRA short-sale files, SEC filings and insider data sets, Wikimedia page views).

## Ideas that cannot be tested cleanly (reported, not counted as hypotheses)
- **ETF-flow price pressure (report idea 10).** Needs historical ETF shares outstanding or per-stock ETF ownership. Neither is free. A stand-in built from ETF trading volume would test a different idea and would add noise to the ledger, so it is not run.
- **LLM-scored earnings-call tone (report idea 6).** An LLM that was trained on text from the test years may already know how those stocks moved afterwards, so a backtest on past years is contaminated (papers in the report). A clean test is a forward record only. Not run; it needs a transcript source with a usable quota and a model run from a pre-registered prompt, started now and judged in a year or more.

## Universe, timing, bar
**Filter rules (126-128).** All 718 point-in-time S&P 500 members with 15:45 snapshots, then the 418 outside the round-9 sample; timing, costs, windows, March 2020 handling exactly as in rounds 11-12 (every 3rd session from the close of 2016-12-30, 15:45 price, fill at the close, book 10% of the ranked names, keep a held name while it is in the top 40%, 5 bps, 10 bps stress, 15:30 price check; IS 2017-2022 and OOS 2023 on; net active >= 2%/yr, IR >= 0.3, placebo >= 0.95, positive at 10 bps and with the 15:30 price; decisions >= 150 / 100). A filter only changes which names are ranked: a name that fails the filter, or has no data for it that day, is not ranked, and the book is 10% of the names left. **Extra rule for filters:** each filter is also compared with a *coverage parent*, the unfiltered parent run on only the names that have data for the filter that day, in the same session. **Supported only if it passes the bar on both the 718 and the 418 and its net active beats the coverage parent's in both windows.** (A filter that does not beat its own parent adds nothing even if it passes.)

**Event rules (129-132).** Each trade: signed abnormal return = sign x (log return of the stock from the entry close to the exit close minus the mean log return of the point-in-time S&P 500 members priced at both closes over the same dates), minus 5 bps at entry and 5 bps at exit. Trades are assigned to a window by entry date (IS 2017-01-01 to 2022-12-31, OOS 2023-01-01 on). Bar per window: mean net per trade >= 25 bps (the round-12 pre-FOMC precedent); cluster-robust t >= 2.0 (clusters = ISO week of entry); placebo >= 0.95 (1000 draws, seed 0: same number of trades, each with a random entry session in the window and a random member priced then, the trade's own hold length and sign; percentile of the actual mean); mean net still > 0 at 10 bps per side. Trades dated 2020-03-09 to 2020-03-20 are dropped. Minimum trades per window as stated for each rule, else "inconclusive". Event data covers current S&P 500 members only (EDGAR files by current company number), so there is survivorship in who can be traded; the benchmark is the point-in-time members, which blunts but does not remove it.

**SPY rule (132)** has one instrument; its bar is annualised net return (mean net per trade x trades per year, position 100%) >= 2%, plus the same t, placebo and 10 bps conditions.

**Weekday rule (133)** uses the filter-rule portfolio bar (net active >= 2%/yr, IR >= 0.3, placebo >= 0.95, positive at 10 bps) with decisions every session, on all 718 and the 418; decisions >= 250 / 150.

## Rules (exact)

**126. Short-sale volume filter, `rev5sv_h3_band40_s`** (data: FINRA consolidated daily short-sale volume files, `CNMSshvol<date>.txt`, member tickers only; files exist from late 2018, so windows for this rule are **IS 2019-01-01 to 2022-12-31** and OOS 2023 on; the first decision with data is the first decision on or after 2019-01-02). For name i on decision day t: SV5 = sum of ShortVolume over sessions t-5..t-1 divided by the sum of TotalVolume over the same sessions (day t is not used: the file is published after the close). Needs all five days. Ranked only if SV5 is at or below the median SV5 of the names that have it that day (the "less short selling" half). Signal rev5 as in the parent. Coverage parent = rev5 on names with SV5. Reported without a verdict: the opposite half (`rev5sv_hi`, names above the median).

**127. No-news filter, `rev5nn_h3_band40_s`** (data: every 8-K of the current S&P 500 from SEC submissions: acceptance time and item list; names with no company number, which are those that left the index, are not ranked). A name is not ranked if it has any 8-K with acceptance time after the 16:00 close of session t-5 and before 15:45 of session t (New York time). All items count (earnings releases included). Coverage parent = rev5 on names with a company number. Reported without a verdict: the names that do have such a filing (`rev5nn_news`).

**128. Attention filter, `rev5wk_h3_band40_s`** (data: Wikimedia daily page views, all-access, user agent, of each current member's English Wikipedia article from 2015-07-01; names whose article is missing are not ranked). Attention ratio for name i on day t = mean daily views over sessions t-5..t-1 divided by the mean over sessions t-65..t-6 (calendar days of the Wikipedia series mapped to sessions; weekends dropped). Ranked only if the ratio is above the median ratio of the names that have it that day (the "more attention than usual" half). Coverage parent = rev5 on names with a ratio. Reported without a verdict: the other half (`rev5wk_lo`).

**129. Peer earnings read-through fade, `peer_fade_s`.** Reporter R: any current member with an earnings release (8-K Item 2.02 from `core.edgar`) whose reaction session s (core.edgar.reaction_sessions) has |abnormal return| >= 5%, where abnormal return = the stock's close-to-close log return on s minus the mean over the point-in-time members. Peers of R: current members with the same two-digit SIC code (groups of at least 5 names with codes, as in `core.industry`), excluding R. A peer is eligible if (a) it has no earnings reaction session in the 40 sessions up to and including s, and (b) it has an expected reaction session: for each of the peer's earlier reaction sessions q dated 330 to 400 calendar days before s, take q plus 364 calendar days, mapped to the first session on or after it; the earliest such date that falls 2 to 30 sessions after s is the expected reaction session (no peer date found: not eligible). Trade: enter at the close of session s+1, exit at the close of the session before the expected reaction session; sign = minus the sign of R's abnormal return (fade). One trade per eligible (R, peer) pair. Minimum 150 / 100 trades. Reported: the legs separately (fade after good news, fade after bad news), and the same trade with exit 10 sessions after entry instead.

**130. Hold into earnings, `earn_premium_s`.** Every current member's earnings reaction session e (as above), long: enter at the close of the 5th session before e, exit at the close of the first session after e. (Release dates are announced weeks ahead, so the entry date is knowable; the reaction session is not known to be before or after the open until the release, so the entry uses the session counts only.) Minimum 150 / 100 trades; note that trades overlap heavily within an earnings season, hence the clustered t.

**131. Insider cluster buys, `insider_cluster_s`** (data: SEC Insider Transactions Data Sets, Form 4 and 4/A, code P open-market purchases, acquired; reporting person an officer or director, not only a 10% owner; purchase value shares x price >= $25,000; issuer matched to a current member by company number). Event: the filing date on which a second distinct insider purchase for the same issuer appears within 10 trading days of the first (filing dates). Enter at the close of the session after that filing date; exit 21 sessions later; one trade per issuer per 60 sessions. Minimum 40 / 20 trades. Not tested: the routine-versus-opportunistic split (needs three years of each insider's history).

**132. End-of-day SPY flow, `spy_eod_flow_s`** (data: SPY 15-minute bars; 15:45 price). Signal r = SPY price at 15:45 over the previous close minus 1. If |r| >= 1.0% enter in the direction of r at the 15:45 price (the price at the 15:45 snapshot) and exit at the close; 5 bps each way. Minimum 100 / 60 trades. This is the rough, price-only form of the leveraged-ETF and option-hedging flow idea; the gamma-based form needs option open interest we do not have.

**133. Same-weekday seasonality, `weekday_seasonal_s`.** On each session t (decision at the close, using only closes up to t), for the weekday w of the next session: for each ranked member, the mean excess log return (stock minus the mean over the members) of its last 20 sessions on weekday w; at least 15 present. Book = top 10% of the ranked names, equal weight, held from the close of t to the close of the next session, rebalanced every session, 5 bps on turnover. Benchmark = equal-weight members. Windows IS 2017-2022 and OOS 2023 on.

## Reporting rules
Every rule gets a table (net active or mean net per trade, IR or t, placebo, turnover, break-even cost, 10 bps, windows, trades) plus its parent where it has one. A rule is not called a candidate if gross is under the bar's cost-free equivalent in both windows. Nothing is added to the shadow or paper records until Garret says so. The count of hypotheses after this round is 133, so about 6 of 133 at a 5% level are expected to pass by chance; the placebo and two-window rules above are the guard against that, not a fix for it.

## Limits (known before running)
- Events and the 8-K and Wikipedia data cover current members only (survivorship); filter rules 127 and 128 are compared with coverage parents for that reason.
- The short-sale files count only off-exchange (FINRA-reported) short volume of each day and include market-maker hedging; the ratio is a noisy proxy for informed shorting.
- Wikipedia titles can redirect or be renamed; names whose title returns no data are dropped, which could bias the sample toward stable names.
- Insider purchases by S&P 500 officers and directors are rare; sample sizes may leave the rule inconclusive.
- Peer groups use two-digit SIC codes, which are coarse; "peer" is a statistical grouping, not a customer or competitor list.

## Amendment 1 (written before any filter result was seen)
The 15-minute price download for 718 names is far slower than in earlier rounds (the data provider rate-limits and each name needs several large pages; about one name a minute after the first hour). Rules 126-128 are therefore run first as a **daily-close screen**: the signal is read at the official close instead of 15:45, everything else is as above (fill at the close, same decisions, same costs, same coverage parent, same bar, same windows, no 15:30 check). The screen cannot be filled in practice, so **a screen pass is never "supported"**: it is "testing" until the same rule passes with 15:45 snapshots on both universes (the download keeps running; the confirmation is run if and when the data arrives, and only for rules that pass the screen). A screen fail is reported as a fail of the filter idea, not as proof about the 15:45 version. Event, SPY and weekday rules are unaffected (SPY needs only its own 15-minute bars).

## Results (run 2026-10-15; hypotheses tested after this round: 133)

**Verdict: 0 of 8 supported. 5 rejected (peer fade, hold into earnings, insider cluster buys, SPY end-of-day flow, same-weekday seasonality), 1 rejected as a filter (Wikipedia attention), 2 left at "testing" (short-sale filter and no-news filter) because they pass the daily-close screen but fail the pre-registered rule that a filter must beat its coverage parent in both windows, and no 15:45 confirmation could be run.** Ledger rows 126-133 carry the numbers. Nothing is added to shadow or paper records.

### Plain English
- **Same-weekday patterns (133):** no pattern. Trading daily on it loses money before costs in 2017-2022 and costs eat the small gain after.
- **Fading peers of a big earnings mover (129):** no. The stocks tended to keep moving the same way as the reporter, the opposite of the idea, and only after good news in 2023 on (gross -96 bps per trade there). I did not flip the rule; flipping it would be a new idea, tested on the same data.
- **Holding into earnings (130):** the premium is there but small: about +18 to +22 bps before costs per trade, +8 to +12 after, short of the 25 bps bar and not statistically solid.
- **Insider cluster buys (131):** looks positive (+24 and +39 bps per trade after costs) but there are only 273 and 159 trades and the result is within chance (t 0.4 and 0.7).
- **SPY into the close after a 1% day (132):** nothing. Slightly negative before costs.
- **Wikipedia attention filter (128):** worse than not filtering in 2017-2022, so rejected.
- **Short-sale filter (126) and no-news filter (127):** the interesting ones. Both pick a subset of the reversal rule's stocks that did far better since 2023 (about 10% a year against about 4% for the plain rule on the 718 names, and the opposite subset lost 2% to 3%). But in the earlier years they added nothing or slightly less, so they miss the rule I wrote down in advance. The pattern also points to a regime change around 2023, which I only saw after the fact. Treat it as a lead to confirm, not a result.

### Rules 126-128 (daily-close screen, see Amendment 1; windows: 126 IS 2019-2022, 127-128 IS 2017-2022; OOS 2023 on; net active %/yr, 5 bps; IR; 10 bps in the last column; "cov" = coverage parent)

**All 718 names.** Parent `rev5_h3_band40_s` on the same screen: IS +7.0 / OOS +4.1.

| Rule | Ranked names | Net active IS / OOS | IR IS / OOS | Placebo IS / OOS | Gross IS / OOS | 10 bps IS / OOS | Turnover IS / OOS |
|---|---|---|---|---|---|---|---|
| 126 sv test (low short-sale share) | 210 | +9.1 / +9.9 | 0.59 / 0.69 | 1.00 / 1.00 | 13.3 / 14.0 | +5.0 / +5.8 | 84 / 83 |
| 126 sv coverage parent | 419 | +10.8 / +4.3 | 0.73 / 0.34 | 1.00 / 1.00 | 14.2 / 7.7 | +7.3 / +0.9 | 70 / 69 |
| 126 opposite half (report) | 209 | +7.6 / -3.4 | 0.48 / -0.26 | 1.00 / 0.84 | 12.0 / 0.9 | +3.3 / -7.7 | 88 / 87 |
| 127 nn test (no 8-K) | 320 | +7.4 / +11.1 | 0.62 / 0.86 | 1.00 / 1.00 | 11.6 / 15.2 | +3.2 / +6.9 | 85 / 84 |
| 127 nn coverage parent | 413 | +7.5 / +7.6 | 0.65 / 0.62 | 1.00 / 1.00 | 10.9 / 11.0 | +4.0 / +4.2 | 69 / 69 |
| 127 names with an 8-K (report) | 93 | -2.2 / -2.5 | -0.14 / -0.14 | 0.58 / 0.52 | 3.5 / 3.3 | -7.9 / -8.3 | 114 / 117 |
| 128 wk test (more attention) | 185 | +3.5 / +7.9 | 0.28 / 0.62 | 0.97 / 1.00 | 7.8 / 12.3 | -0.9 / +3.5 | 88 / 89 |
| 128 wk coverage parent | 370 | +7.2 / +10.2 | 0.64 / 0.82 | 1.00 / 1.00 | 10.7 / 13.7 | +3.8 / +6.8 | 69 / 70 |

**The 418 unseen names.** Parent: IS +5.1 / OOS +3.7.

| Rule | Ranked names | Net active IS / OOS | IR IS / OOS | Placebo IS / OOS | 10 bps IS / OOS | Verdict IS / OOS |
|---|---|---|---|---|---|---|
| 126 sv test | 123 | +6.0 / +7.7 | 0.38 / 0.50 | 0.99 / 1.00 | +1.8 / +3.6 | supports / supports |
| 126 sv coverage parent | 245 | +8.7 / +3.9 | 0.60 / 0.30 | 1.00 / 1.00 | +5.2 / +0.4 | supports / contradicts |
| 127 nn test | 188 | +8.3 / +10.2 | 0.66 / 0.75 | 1.00 / 1.00 | +4.1 / +6.0 | supports / supports |
| 127 nn coverage parent | 242 | +7.2 / +6.0 | 0.61 / 0.45 | 1.00 / 1.00 | +3.8 / +2.5 | supports / supports |
| 128 wk test | 110 | +2.7 / +10.9 | 0.20 / 0.75 | 0.92 / 1.00 | -1.7 / +6.5 | contradicts / supports |
| 128 wk coverage parent | 220 | +8.1 / +9.0 | 0.70 / 0.66 | 1.00 / 1.00 | +4.6 / +5.5 | supports / supports |

Reading the rule: 126 beats its coverage parent in OOS (+9.9 vs +4.3; +7.7 vs +3.9) but not in IS (+9.1 vs +10.8; +6.0 vs +8.7), so it is not supported. 127 beats its coverage parent in OOS (+11.1 vs +7.6; +10.2 vs +6.0) and on the 418 in IS (+8.3 vs +7.2), but ties it in IS on the 718 (+7.4 vs +7.5), so it is not supported. 128 is below its coverage parent in IS on both sets and rejected. The coverage parents matter: restricting to names with filing history alone (current members) lifts the OOS parent from +4.1 to +7.6 (survivorship), so the unfiltered numbers would have overstated the no-news filter by about half.

### Rules 129-133 (event rules: per trade net of 5 bps each way; weekday: portfolio bar)

| Rule | Window | Trades | Gross / net bps per trade | Cluster t | Placebo | 10 bps per side net | Verdict |
|---|---|---|---|---|---|---|---|
| 129 peer_fade_s | IS | 13,326 | -8.3 / -18.3 | -1.25 | 0.03 | -28.3 | contradicts |
| | OOS | 13,534 | -15.4 / -25.4 | -2.11 | 0.00 | -35.4 | contradicts |
| 130 earn_premium_s | IS | 11,626 | +18.3 / +8.3 | 1.08 | 1.00 | -1.7 | contradicts |
| | OOS | 7,711 | +21.6 / +11.6 | 1.07 | 1.00 | +1.6 | contradicts |
| 131 insider_cluster_s | IS | 273 | +33.8 / +23.8 | 0.38 | 0.72 | +13.8 | contradicts |
| | OOS | 159 | +48.5 / +38.5 | 0.71 | 0.74 | +28.5 | contradicts |
| 132 spy_eod_flow_s | IS | 369 | -0.7 / -10.7 | -6.32 | 0.30 | -20.7 | contradicts |
| | OOS | 204 | -3.7 / -13.7 | -7.13 | 0.00 | -23.7 | contradicts |

Report-only splits of 129: after good news IS -4.9 gross (t -0.56), OOS -95.7 (t -4.41); after bad news IS -11.6, OOS +57.4 gross (t +2.19); the signs disagree across windows, so no consistent version of the fade or its reverse exists. Exit after at most 10 sessions instead of the expected report date: IS -6.4, OOS -14.2 gross.

| Rule | Universe | Net active IS / OOS | IR IS / OOS | Placebo IS / OOS | Gross IS / OOS | Turnover | 10 bps IS / OOS | Verdict |
|---|---|---|---|---|---|---|---|---|
| 133 weekday_seasonal_s | 719 names | -28.8 / -9.9 | -2.96 / -0.81 | 0.00 / 1.00 | -6.6 / +11.8 | 445x / 435x | -51.0 / -31.6 | contradicts |
| | 419 names | -27.1 / -8.8 | -2.78 / -0.69 | 0.00 / 1.00 | -4.7 / +13.0 | 449x / 435x | -49.5 / -30.5 | contradicts |

### What this round did not settle
- 126 and 127 on 15:45 snapshots: the intraday download did not finish (about 35 of 297 sample names after an hour; the data provider rate-limited it). The screen reads the signal at the close, which the parent's results show is close (parent IS +7.0 / OOS +4.1 on the screen against +7.9 / +4.9 at 15:45). A confirmation run on the 15:45 data, with a pre-registered test of the split between the early and later years, is the natural next step if you want one.
- The daily short-sale files exist only from 2018-08, so rule 126's "earlier years" are 2019-2022 only.
- 8-K, Wikipedia and event data cover current members only; Wikipedia titles failed for 38 of 502 members.
- Not run: ETF-flow pressure and LLM-scored transcripts (see above).
- Evidence-since-publication check: the ranked report of the same date is that check.
