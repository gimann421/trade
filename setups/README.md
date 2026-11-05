# Setups (not rule-search hypotheses)
Built to be run, not to pass the multiple-testing bar. Simulation only; no orders, no accounts.
- `polymarket_lag/recorder.py`: records Polymarket 5-min BTC Up/Down order book + Coinbase spot every 2s, simulates a lag-detector trade at the real ask incl. taker fee, settles on Polymarket's outcome. `report` prints P&L. Data in `polymarket_lag/data/` (not committed).
- `swing_h4/swing.py`: BTC H4 Donchian-55 and SMA50/200 paper accounts, writes `status.html` (phone-sized one-pager) and `state.json`.
Real money, accounts, or trading on Polymarket (US geoblock) need Garret's explicit OK.
