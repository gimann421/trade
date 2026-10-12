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
| `config/`      | Risk limits and API keys (`.env`); only `*.example` is tracked | no      |
| `data/`        | Historical prices                                              | no      |

## Rules

- Broker access goes through `alpaca-py` with `paper=True`. Never connect a live-money account.
- Keys live in `config/.env` (see `config/.env.example`). Never print or log them.
- A changed strategy gets a new file with the next version number; old versions stay so
  backtests and journal entries can point at the exact code they used.

## Setup

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp config/.env.example config/.env   # then add your paper keys
```
