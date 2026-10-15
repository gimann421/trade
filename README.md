# trade

An AI-assisted trading research loop. **Paper trading only.**

## Layout

| Directory      | Purpose                                                        | In git? |
|----------------|----------------------------------------------------------------|---------|
| `research/`    | Idea memos, one per idea                                       | yes     |
| `strategies/`  | Strategy code, one file per strategy version: `<name>_v<N>.py` | yes     |
| `backtests/`   | Backtest results                                               | yes     |
| `journal/`     | Every paper-trading decision and the reasoning behind it       | yes     |
| `paper/`       | Forward shadow record of rules that passed (nav, decisions)    | yes     |
| `memory/`      | Hypothesis ledger (SQLite)                                     | yes     |
| `config/`      | `risk_limits.yaml` (tracked) and API keys in `.env` (ignored)  | partly  |
| `data/`        | Historical prices                                              | no      |
| `core/`        | Shared code: broker, risk, journal, ledger, data, backtester   | yes     |

## Rules

- All broker access goes through `core.broker.get_paper_client()`. It forces `paper=True`,
  checks the endpoint is Alpaca's paper API, and checks the account number starts with `PA`.
  Never build a `TradingClient` directly, and never connect a live-money account.
- Orders go through `core.broker.submit_order()`, which checks `config/risk_limits.yaml`
  and journals the decision (sent, blocked or failed) with its reasoning. Record holds and
  skips with `core.journal.record()`.
- Keys live in `config/.env` (see `config/.env.example`). If that file is missing or sets neither
  key, `ALPACA_PAPER_API_KEY` / `ALPACA_PAPER_SECRET_KEY` are read from the environment instead.
  Never print or log them.
- A changed strategy gets a new file with the next version number; old versions stay so
  backtests and journal entries can point at the exact code they used.

## Setup

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp config/.env.example config/.env   # then add your paper keys
python -m pytest tests
```

Check the connection (prints account status and equity only, never keys):

```sh
python -c "from core.broker import get_paper_client as g; a=g().get_account(); print(a.status, a.equity)"
```

## The loop

1. Write a memo in `research/` from `research/TEMPLATE.md` and add the hypothesis to the ledger.
2. Write `strategies/<name>_v1.py`: `VERSION = 1` and `generate_signals(bars)` returning
   target weights in [-1, 1]. See `strategies/sma_crossover_v1.py`.
3. Get data (needs keys): `python -m core.data SPY --start 2016-01-01`
4. Backtest: `python -m core.backtest strategies/<name>_v1.py SPY --hypothesis-id 1 --verdict supports`
   The backtester rejects strategies that use future data and compares against buy-and-hold.
   Strategies that allocate across several symbols define `generate_weights(bars_by_symbol)`
   instead and run with `python -m core.portfolio strategies/<name>_v1.py SPY EFA TLT --start 2023-01-01`;
   see the `core/portfolio.py` docstring for the weights contract and the benchmarks each run is scored against.
5. Paper trade through `submit_order()`; every decision lands in `journal/`.
   Rules marked `supported` are first tracked forward by `core/paper_runner.py`: list them in
   `paper/tracked.json` and run `python -m core.paper_runner run` after each close. It rebuilds a
   shadow portfolio from the start date (same code as the backtest), writes `paper/<rule>/nav.csv`
   and one never-overwritten `decisions/<date>.json` per month-end, and sends nothing to a broker.
   `--execute` places paper orders through `submit_order()` only for rules whose `allocation_pct`
   is above 0. `python -m core.paper_runner preview <rule>` prints the current picks without writing.
   Rules that pass the bar in all three eras (2016-22, 2023+, 2000-15) also get a forward record, as a
   `kind: "signal"` entry (single-symbol, shadow only, `core/signal_tracker.py`). `python research/three_era_screen.py`
   prints the chance those passers are luck and an ALERT line if it reaches 10% (`research/screen-funnel-2026-10-14.md`).

## Paper orders for every passing rule

Each rule in `paper/tracked.json` with `allocation_pct` above 0 has its own sleeve inside the one paper account
(`core/sleeves.py`): its orders carry a `client_order_id` starting with the rule id, and its shares are rebuilt from the
filled quantities of those orders, so rules that hold the same stock never touch each other's shares. The shadow record
stays the official scoreboard. Sleeve sizes add up to 135% of equity (limit 150).

- Month-end stock rules and the XLK signal rule: `python -m core.paper_runner run --execute` after the close (DAY market orders, filled at the next open; the shadow record assumes the close).
- 15:45 reversal rules: `python -m core.snapshot_orders --execute` on a session, started a few minutes before 15:45. It waits for the 15:30 bar, writes the decision file, and sends market-on-close orders before the 15:50 cut-off. Without `--execute` it is a dry run.
