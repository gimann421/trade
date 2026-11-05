# r64: Polymarket BTC lag and H4 swing (hyp 278-281)

## Polymarket 5-minute BTC Up/Down (hyp 278, not testable on free data)
- Reachable: gamma-api and clob.polymarket.com, Coinbase 1m candles. Binance is geo-blocked.
- Markets: 5 and 15 minute, resolve on Chainlink BTC/USD 60s TWAP. Taker fee = 0.07*p*(1-p) per share (about 1.75c at 50c), 20% rebate to makers.
- polymarket.com/api/geoblock reports blocked for this container's US IP; US legality for Garret unverified.
- Backtest (3 days, 864 markets, fair value = normal model on Coinbase return since window open): apparent +13c/share, t~9, but the edge GROWS as the Polymarket price gets staler (lag 0s +14c, 60s +18c, 120s +25c) and a sign-flipped placebo loses -17c. The history endpoint is sparse last-trade data (median 42s old), not executable quotes. This is a stale-price artifact, not evidence of a lag. A real test needs order-book snapshots (not available historically); would need a forward recorder polling /book every second.
## BTC-USD H4 swing (hyp 279-281; Coinbase hourly 2016-2026, 10 bps/side)
- Donchian55: IS 2016-21 +87.8%/yr (Sharpe 1.69) vs buy&hold +107.7% (1.39); OOS 2022+ +21.3% (0.66) vs +23.6% (0.48).
- SMA50/200: IS +91.3% (1.61), OOS +15.2% (0.47 vs 0.48).
- RSI pullback in uptrend: ~0 both eras.
- Verdict: no pass. Trend rules cut drawdown and lift Sharpe slightly but earn less than holding; this is BTC's own drift, not a new edge. Prop firms mainly trade FX/gold/indices, which are not reachable here at H1/H4.
