"""Hypothesis: Polymarket 5-min BTC Up/Down odds lag spot BTC (Coinbase 1m).
Pre-registered rule: at minute m in {1,2,3,4} of a 5-min window, fair=Phi(ret/(sigma*sqrt(rem)));
buy the cheap side if edge > fee + assumed spread (S cents), hold to resolution.
Run: python research/r64_polymarket_lag.py DAYS"""
import sys, json, time, math, urllib.request, concurrent.futures as cf
import numpy as np
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
def get(u, tries=3):
    for i in range(tries):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"research"}), timeout=30))
        except Exception: time.sleep(1+i)
def coinbase(start, end):
    out = {}
    t = start
    while t < end:
        e = min(t + 300*60, end)
        iso = lambda x: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(x))
        d = get(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60&start={iso(t)}&end={iso(e)}")
        for c in d or []: out[c[0]+60] = c[4]  # price AT time c[0]+60 (close of the minute that just ended)
        t = e
    return out
def market(ts):
    d = get(f"https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{ts}")
    if not d: return None
    m = d[0]["markets"][0]
    if not m.get("closed") or json.loads(m["outcomePrices"])[0] not in ("0","1"): return None
    up = json.loads(m["clobTokenIds"])[0]
    h = get(f"https://clob.polymarket.com/prices-history?market={up}&startTs={ts-60}&endTs={ts+330}&fidelity=1")
    return ts, json.loads(m["outcomePrices"])[0] == "1", (h or {}).get("history", [])
now = int(time.time()); end = now//300*300 - 600; start = end - DAYS*86400
px = coinbase(start-3600, end+600); print("btc minutes", len(px))
tss = list(range(start, end, 300))
with cf.ThreadPoolExecutor(8) as ex: mk = [r for r in ex.map(market, tss) if r]
print("markets", len(mk), "of", len(tss))
json.dump(mk, open("/tmp/r64_markets.json", "w"))
from math import erf, sqrt
Phi = lambda x: 0.5*(1+erf(x/sqrt(2)))
def run(S, thr, ms=(1,2,3,4)):
    pnl = []
    for ts, up_won, h in mk:
        if len(h) < 3: continue
        if ts not in px: continue
        # trailing 1-min vol over previous 60 minutes
        r = [math.log(px[ts-60*i]/px[ts-60*(i+1)]) for i in range(1,61) if ts-60*(i+1) in px and ts-60*i in px]
        if len(r) < 30: continue
        sg = np.std(r)
        for m in ms:
            t = ts + 60*m
            if t not in px: continue
            prev = [x for x in h if x["t"] <= t]
            if not prev: continue
            p = prev[-1]["p"]  # Up price (last observed)
            ret = math.log(px[t]/px[ts]) if ts in px else None
            if ret is None: continue
            fair = Phi(ret/(sg*sqrt(5-m))) if m<5 else 0.5
            for side, price, win in (("up", p, up_won), ("dn", 1-p, not up_won)):
                f = fair if side=="up" else 1-fair
                cost = price + S
                fee = 0.07*cost*(1-cost)
                if f - cost - fee > thr and 0.05 < price < 0.95:
                    pnl.append((ts, (1 if win else 0) - cost - fee)); break
            else: continue
            break  # one trade per market
    return pnl
for S in (0.0, 0.01, 0.02, 0.03):
    for thr in (0.03, 0.06, 0.10):
        p = run(S, thr); a = np.array([x[1] for x in p])
        if len(a): print(f"spread {S:.2f} thr {thr:.2f} n={len(a)} mean/share {a.mean():+.4f} se {a.std()/math.sqrt(len(a)):.4f} t={a.mean()/(a.std()/math.sqrt(len(a))+1e-9):+.2f}")
