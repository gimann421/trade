# Calendar effects on SPY/QQQ: turn-of-month, pre-holiday, options-expiration week

- **Date:** 2026-10-12
- **Ledger hypothesis id:** 11 (turn-of-month), 12 (pre-holiday), 13 (options-expiration week)
- **Strategy file:** TBD

Author: seasonality-analyst. Only date-driven rules on daily bars. No returns were computed and
no parameters were tested on `data/` before writing this. Every window and parameter below is
fixed now and comes from published work.

Ledger check (2026-10-12): hypotheses 1-10 are trend, volatility and mean-reversion ideas
(SMA crossover, vol targeting, TSMOM ladder, Donchian, RSI(2), down-streaks, IBS, vol-ratio,
gap-down cluster, range-shock timeout). None are calendar ideas, and none are 'rejected'. These
three ideas do not repeat any of them, and none of them uses price at all: the position depends
only on the date.

## Common definitions (apply to all three ideas)

**Trading calendar.** A trading day is any weekday that is not a scheduled NYSE full-day
holiday. The holidays come from fixed rules (built with `pandas.tseries.holiday`, never from gaps
in the data file):

- New Year's Day: Jan 1, or Mon Jan 2 if Jan 1 is a Sunday. Nothing is observed when Jan 1 is
  a Saturday (NYSE rule 7.2).
- Martin Luther King Jr. Day: 3rd Monday of January.
- Washington's Birthday: 3rd Monday of February.
- Good Friday.
- Memorial Day: last Monday of May.
- Juneteenth: Jun 19 from 2022 on. A Saturday moves to Friday and a Sunday moves to Monday.
- Independence Day: Jul 4, with the same Saturday/Sunday shift.
- Labor Day: 1st Monday of September.
- Thanksgiving: 4th Thursday of November.
- Christmas: Dec 25, with the same Saturday/Sunday shift.

Unscheduled closures (2018-12-05 Bush funeral, 2025-01-09 Carter funeral) are **not** holidays
in this calendar. They were not known far in advance, and leaving them out keeps the rule
mechanical. If such a date is a trading day in the calendar but has no bar, it simply gets no
return. Half-days (Jul 3, the day after Thanksgiving, Dec 24) are ordinary trading days.
`next_td(t)` means the next trading day after t in this calendar. Because the rules are fixed,
it is known at t's close.

**Backtester timing.** `generate_signals(bars)` returns a weight w_t for each bar date t,
computed from t's date only. The backtester holds w_t over day t+1's close-to-close return and
charges 5 bps per unit of turnover. Every rule below is stated as "w_t = 1 iff `next_td(t)` is
an *in-window* day, else 0". So "in-window day d" means we are long over d's close-to-close
return: we buy at the close of the trading day before d and sell at d's close, unless the next
day is also in-window. Weights are only 0 or 1, never short (`allow_short: false`).

**Evaluation (same procedure for all three).** Signals are computed on the full history and the
daily net returns are then cut into two windows: IS 2016-01-01..2022-12-31 and OOS
2023-01-01..2026-10-09. The test runs separately for SPY and QQQ at 5 bps. The benchmark is
buy-and-hold on the same symbol over the same dates. Definitions:

- *exposure days* = days with position > 0.
- *net return per exposure day* = sum of daily net strategy returns / number of exposure days.
- *B&H mean daily return* = mean of buy-and-hold daily returns over the same dates.
- *Sharpe* = annualized, computed as in `core/backtest._metrics`, with zero-return days included.

**An idea is supported only if it passes its kill test in both windows on both SPY and QQQ.**
These effects are claimed for the broad US large-cap market, so they should show up in both
ETFs. A window with fewer than 20 entries counts as inconclusive, not supported.

Multiple testing: 3 ideas x 2 symbols x 2 windows. Each threshold is set well above what random
timing would give at the same exposure, so a pass is not a coin-flip.

---

## Idea 1 (hypothesis 11): Turn-of-month window, days -1 to +3

### Hypothesis
Holding SPY/QQQ only over the last trading day of each month and the first three trading days
of the next month (w_t = 1 iff `next_td(t)` is month-day -1, +1, +2 or +3; that is, enter at the
close of day -2 and exit at the close of day +3, about 4 of 21 days or 19% exposure) earns at
least 2x buy-and-hold's mean daily return per day in the market and a Sharpe at least equal to
buy-and-hold's, after 5 bps costs.

### Why it might work
The window [-1, +3] is the standard one from Lakonishok & Smidt (1988), Ariel (1987) and
McConnell & Xu (2008). McConnell & Xu found that from 1926 to 2005 essentially all of the US
equity premium was earned in this window, and that the effect held up after 1987 and was not
just a small-cap effect. The proposed cause is flows that arrive on fixed dates:

- payroll-linked 401(k) and other defined-contribution contributions;
- month-start pension and fund cash investment;
- dividend and coupon reinvestment;
- month-end window dressing and NAV marking by institutions.

Ogden (1990) ties the effect to the timing of payments. The other side is anyone supplying
shares into those predictable inflows (market makers, short-term sellers) and selling a little
too cheaply. The trade is cheap to run (2 trades per month, about 1.2%/yr in costs at 5 bps).
It persists because benchmarked money cannot be out of the market for the other 80% of days.

### Market conditions it needs
- Regular month-boundary inflows into US large-cap equities, which holds in any normal regime.
- No market-wide shock clustered in the off-window days. This rule does not dodge crashes; it
  only avoids about 80% of days at random with respect to news.
- Works in any trend or volatility regime. It does not need a bull market, because the test is
  relative to buy-and-hold over the same dates.

### How it could fail (kill threshold, fixed now)
Per symbol, per window (IS 2016-2022, OOS 2023-2026-10-09), 5 bps. **Kill** if either:
- net return per exposure day < 2.0 x B&H mean daily return, or
- annualized Sharpe < buy-and-hold Sharpe on the same dates.

Must pass both windows on **both SPY and QQQ**. If this window earns about what a random 19% of
days earns, the flow mechanism is gone or was arbitraged away after publication. Fewer than 20
entries in a window is inconclusive (expected: ~84 IS, ~45 OOS).

### Test plan
SPY and QQQ, `data/*_1Day.csv`, 2016-01-04..2026-10-09, 5 bps, benchmark buy-and-hold same
symbol. No parameters to tune: the window is fixed at [-1, +3] by the literature.

### Results
TBD

---

## Idea 2 (hypothesis 12): Pre-holiday day

### Hypothesis
Holding SPY/QQQ only over the last trading day before each scheduled NYSE full-day holiday
(w_t = 1 iff `next_td(t)` is a pre-holiday day, defined below; about 9-10 days/yr or ~4%
exposure) earns at least 3x buy-and-hold's mean daily return per day in the market and a Sharpe
of at least 0.5x buy-and-hold's, after 5 bps costs.

Precisely: day d is a *pre-holiday day* if d is a trading day and the next weekday after d is
a scheduled holiday from the list above. Weekends between d and the holiday are allowed, so the
Friday before a Monday holiday qualifies. w_t = 1 iff `next_td(t)` is a pre-holiday day.

### Why it might work
The pre-holiday effect has been documented for over a century of US data: Ariel (1990),
Lakonishok & Smidt (1988), Kim & Park (1994). In those samples the average pre-holiday return
was roughly 9-14x the average day. Proposed causes:

- Short sellers and market makers cover before a long closure rather than carry overnight risk
  over the holiday.
- Retail and institutional mood improves ahead of holidays.
- Lower volume means small net buying moves prices further.

The other side is liquidity providers and shorts who need to flatten before an extended close.
They pay a premium for not holding risk over the closure.

What changed / risk: some later studies report the effect weakened after the early 1990s. That
is why the bar is 3x, not the historical 9x+. The OOS window will show whether anything is left.

### Market conditions it needs
- A scheduled multi-day or long-weekend closure that makes short positions or inventory costly
  to carry, which is true every year.
- At ~4% exposure, one bad pre-holiday day (for example a crash-day eve) can dominate a window.
  The idea assumes the effect is broad and not driven by one or two outliers.

### How it could fail (kill threshold, fixed now)
Per symbol, per window, 5 bps. **Kill** if either:
- net return per exposure day < 3.0 x B&H mean daily return, or
- annualized Sharpe < 0.5 x buy-and-hold Sharpe on the same dates.

The Sharpe bar is scaled down because at 4% exposure, holding the same per-day edge as
buy-and-hold would give only about sqrt(0.04) = 0.2x B&H Sharpe. 0.5x is roughly what a
genuine ~3x per-day edge would give.

Must pass both windows on **both SPY and QQQ**. Fewer than 20 entries in a window is
inconclusive (expected: ~69 IS, ~38 OOS).

### Test plan
SPY and QQQ, 2016-01-04..2026-10-09, 5 bps, benchmark buy-and-hold same symbol. Holidays come
from the fixed rule list above. Report the 3 largest pre-holiday returns and the 3 most negative
ones per window, so a result driven by one or two days is visible.

### Results
TBD

---

## Idea 3 (hypothesis 13): Monthly options-expiration week

### Hypothesis
Holding SPY/QQQ only over the trading days of the Monday-Friday calendar week that contains the
third Friday of each month (monthly equity-option expiration week; w_t = 1 iff `next_td(t)` falls
in that week; about 5 of 21 days or 24% exposure) earns at least 2x buy-and-hold's mean daily
return per day in the market and a Sharpe at least equal to buy-and-hold's, after 5 bps costs.

Precisely: for each month, F = the third Friday (by calendar date, days 15-21). The OpEx week is
the Monday-Friday of the calendar week containing F, including F even when F is a holiday (e.g.
Good Friday; expiration then moves to Thursday and the week is unchanged). This window never
overlaps idea 1's turn-of-month days (-1..+3), because OpEx week falls between the 11th and the
21st.

### Why it might work
Stivers & Sun (2013, "Return predictability around monthly option expiration" / "Options
expiration and stock returns") found that US large-cap stocks earned clearly higher returns in
the week ending on monthly options expiration than in other weeks (1983-2010). The proposed
cause is dealer hedging:

- Index and ETF option open interest is skewed toward investors who are long puts and short
  calls, so dealers are short puts / long calls on net and hold short-stock hedges.
- As expiration nears, those options lose delta (time decay, the "charm" effect) and many expire
  worthless.
- Dealers buy back the short-stock hedges, which is a mechanical, price-insensitive buy flow.

The other side is option hedgers, who pay for protection and leave dealers holding hedges that
unwind on a known schedule.

### Market conditions it needs
- Large monthly (third-Friday) open interest in SPX/SPY/QQQ/NDX options with the usual
  put-heavy customer positioning.
- Risk: the shift to daily and 0DTE expirations since 2022 spreads hedging flow across the
  month and may have diluted the monthly cycle. The OOS window (2023-2026) is exactly the period
  where 0DTE dominates, so it tests whether the effect survived that change. A pass IS but a
  failure OOS would point to that structural change.

### How it could fail (kill threshold, fixed now)
Per symbol, per window, 5 bps. **Kill** if either:
- net return per exposure day < 2.0 x B&H mean daily return, or
- annualized Sharpe < buy-and-hold Sharpe on the same dates.

Must pass both windows on **both SPY and QQQ**. Fewer than 20 entries in a window is
inconclusive (expected: ~84 IS, ~45 OOS).

### Test plan
SPY and QQQ, 2016-01-04..2026-10-09, 5 bps, benchmark buy-and-hold same symbol. The third
Friday comes from the calendar, not from any options data. No parameters to tune.

### Results
TBD
