"""H4 swing paper setup on BTC-USD (Coinbase public candles). PAPER ONLY, no broker, no account.
Each run: fetch recent hourly bars -> 4h bars, compute two long/flat trend rules (Donchian-55 breakout,
SMA50/200), mark a $10,000 paper account per rule (10 bps per side), log signal changes, rewrite status.html.
  python setups/swing_h4/swing.py"""
import os, json, time, html, urllib.request, pandas as pd
H = os.path.dirname(__file__); ST = os.path.join(H, "state.json"); CAP = 10000.0; COST = 0.001
def get(u):
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "r"}), timeout=30))
        except Exception: time.sleep(1 + i)
iso = lambda x: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(x))
def bars():
    e = int(time.time()) // 3600 * 3600; rows = []
    for k in range(5):  # ~1500 hourly bars
        a, b = e - (k + 1) * 299 * 3600, e - k * 299 * 3600
        rows += get(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600&start={iso(a)}&end={iso(b)}") or []
    df = pd.DataFrame(rows, columns="t l h o c v".split()).drop_duplicates("t").sort_values("t"); df.index = pd.to_datetime(df.t, unit="s")
    h4 = df.resample("4h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    return h4.iloc[:-1] if time.time() < h4.index[-1].timestamp() + 4 * 3600 else h4  # drop unfinished bar
def signals(c):
    up = c > c.shift(1).rolling(55).max(); dn = c < c.shift(1).rolling(55).min()
    d = pd.Series(float("nan"), index=c.index); d[up] = 1; d[dn] = 0
    return {"donchian55": d.ffill().fillna(0), "sma50_200": (c.rolling(50).mean() > c.rolling(200).mean()).astype(float)}
def main():
    c = bars().c; sig = signals(c); st = json.load(open(ST)) if os.path.exists(ST) else {"rules": {}}
    for k, s in sig.items():
        r = st["rules"].setdefault(k, {"cash": CAP, "btc": 0.0, "last_bar": None, "log": []})
        for t, px in c.items():
            if r["last_bar"] and str(t) <= r["last_bar"]: continue
            if r["last_bar"] is None and t < c.index[-1] - pd.Timedelta(hours=4): continue  # start at latest bar
            want = s[t]; held = r["btc"] > 0
            if want and not held: r["btc"] = r["cash"] * (1 - COST) / px; r["cash"] = 0; r["log"].append([str(t), "BUY", round(px, 2)])
            elif not want and held: r["cash"] = r["btc"] * px * (1 - COST); r["btc"] = 0; r["log"].append([str(t), "SELL", round(px, 2)])
            r["last_bar"] = str(t)
        r["equity"] = r["cash"] + r["btc"] * c.iloc[-1]; r["pos"] = "LONG" if r["btc"] > 0 else "FLAT"
    st["price"] = float(c.iloc[-1]); st["bar"] = str(c.index[-1]); st["updated"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    json.dump(st, open(ST, "w"), indent=1)
    rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{r['pos']}</td><td>${r['equity']:,.0f}</td><td>{len([x for x in r['log']])}</td><td>{html.escape(' '.join(map(str, r['log'][-1])) if r['log'] else '-')}</td></tr>" for k, r in st["rules"].items())
    open(os.path.join(H, "status.html"), "w").write(f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>BTC H4 swing paper</title>
<style>body{{font:16px system-ui;margin:16px;max-width:640px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:6px;border-bottom:1px solid #8884;text-align:left}}</style>
<h2>BTC H4 swing (paper)</h2><p>BTC ${st['price']:,.0f} · last bar {st['bar']} · updated {st['updated']}<br>Paper only: $10,000 start per rule, 10 bps per side.</p>
<table><tr><th>Rule</th><th>Now</th><th>Equity</th><th>Trades</th><th>Last</th></tr>{rows}</table>""")
    print(json.dumps({k: (r["pos"], round(r["equity"])) for k, r in st["rules"].items()}))
main()
