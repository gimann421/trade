# trade

An AI-assisted trading research loop. **Paper trading only.**

## Layout

| Directory      | Purpose                                                        | In git? |
|----------------|----------------------------------------------------------------|---------|
| `research/`    | Idea memos, one per idea                                       | yes     |
| `strategies/`  | Strategy code, one file per strategy version: `<name>_v<N>.py` | yes     |
| `backtests/`   | Backtest results                                               | yes     |
| `journal/`     | Every paper-trading decision and the reasoning behind it       | yes     |
| `memory/`      | Hypothesis ledger (SQLite)                                     | yes     |
| `config/`      | `risk_limits.yaml` (tracked) and API keys in `.env` (ignored)  | partly  |
| `data/`        | Historical prices                                              | no      |
| `core/`        | Shared code: key loading, paper broker, risk limits, ledger    | yes     |

## Rules

- All broker access goes through `core.broker.get_paper_client()`. It forces `paper=True`,
  checks the endpoint is Alpaca's paper API, and checks the account number starts with `PA`.
  Never build a `TradingClient` directly, and never connect a live-money account.
- Keys live in `config/.env` (see `config/.env.example`). Never print or log them.
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
