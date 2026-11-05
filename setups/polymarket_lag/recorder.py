"""Polymarket 5-min BTC Up/Down: live order-book recorder + lag detector with SIMULATED trades.
Read-only public APIs. Places NO orders, needs NO account. Usage:
  python setups/polymarket_lag/recorder.py run --minutes 30      # record + simulate
  python setups/polymarket_lag/recorder.py report                # summarise sim trades
Rule (set in advance): between 60s and 240s into a window, fair P(Up)=Phi(ret/(sigma*sqrt(remaining)))
from Coinbase spot; buy the side whose fair - ask - taker fee(0.07*p*(1-p)) > EDGE; one trade per window,
stake $10 at the quoted ask (size-limited); settle on Polymarket's own outcome after the window closes."""
import sys, os, json, time, math, argparse, urllib.request
from math import erf, sqrt
D = os.path.join(os.path.dirname(__file__), "data"); os.makedirs(D, exist_ok=True)
EDGE, STAKE = 0.05, 10.0
def get(u):
    try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research"}), timeout=10))
    except Exception: return None
Phi = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
def market(ts):
    e = get(f"https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{ts}")
    if not e: return None
    m = e[0]["markets"][0]; return json.loads(m["clobTokenIds"])[0]
def quote(tok):
    b = get(f"https://clob.polymarket.com/book?token_id={tok}")
    if not b or not b["bids"] or not b["asks"]: return None
    bid = max(b["bids"], key=lambda x: float(x["price"])); ask = min(b["asks"], key=lambda x: float(x["price"]))
    return float(bid["price"]), float(bid["size"]), float(ask["price"]), float(ask["size"])
def spot():
    d = get("https://api.coinbase.com/v2/prices/BTC-USD/spot"); return float(d["data"]["amount"]) if d else None
def settle():
    p = os.path.join(D, "sim_trades.jsonl")
    if not os.path.exists(p): return
    rows = [json.loads(l) for l in open(p)]; ch = False
    for r in rows:
        if r.get("won") is None and time.time() > r["ts"] + 330:
            e = get(f"https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{r['ts']}")
            if e and e[0]["markets"][0].get("closed"):
                up_won = json.loads(e[0]["markets"][0]["outcomePrices"])[0] == "1"
                r["won"] = up_won if r["side"] == "up" else (not up_won)
                r["pnl"] = (1 if r["won"] else 0) * r["shares"] - r["cost"]; ch = True
    if ch: open(p, "w").write("".join(json.dumps(r) + "\n" for r in rows))
def run(minutes):
    end = time.time() + minutes * 60; hist = []; cur = None; traded = set()
    while time.time() < end:
        t0 = time.time(); ts = int(t0) // 300 * 300; s = spot()
        if s is None: time.sleep(2); continue
        hist.append((t0, s)); hist = [h for h in hist if t0 - h[0] < 1800]
        if cur is None or cur["ts"] != ts:
            tok = market(ts); cur = {"ts": ts, "tok": tok, "open": s}
            settle()
        if cur["tok"]:
            q = quote(cur["tok"])
            if q:
                bid, bs, ask, asz = q; el = t0 - ts
                open(os.path.join(D, "book_%s.jsonl" % time.strftime("%Y%m%d", time.gmtime(t0))), "a").write(
                    json.dumps({"t": round(t0, 1), "ts": ts, "spot": s, "open": cur["open"], "bid": bid, "ask": ask, "bs": bs, "as": asz}) + "\n")
                if 60 <= el <= 240 and ts not in traded and len(hist) > 60:
                    rets = [math.log(hist[i][1] / hist[i - 1][1]) for i in range(1, len(hist))]
                    dt = (hist[-1][0] - hist[0][0]) / len(rets)
                    sg = (sum(r * r for r in rets) / len(rets)) ** .5 / sqrt(dt)  # per-sqrt-second vol
                    fair = Phi(math.log(s / cur["open"]) / (sg * sqrt(300 - el) + 1e-12))
                    for side, px, f, sz in (("up", ask, fair, asz), ("down", 1 - bid, 1 - fair, bs)):
                        fee = 0.07 * px * (1 - px)
                        if 0.05 < px < 0.95 and f - px - fee > EDGE:
                            shares = min(STAKE / px, sz); cost = shares * (px + fee)
                            open(os.path.join(D, "sim_trades.jsonl"), "a").write(json.dumps({"ts": ts, "t": round(t0, 1), "side": side, "price": px, "fair": round(f, 3), "fee": round(fee, 4), "shares": round(shares, 2), "cost": round(cost, 2), "won": None}) + "\n")
                            traded.add(ts); break
        time.sleep(max(0, 2 - (time.time() - t0)))
    settle()
def report():
    p = os.path.join(D, "sim_trades.jsonl"); rows = [json.loads(l) for l in open(p)] if os.path.exists(p) else []
    done = [r for r in rows if r.get("won") is not None]
    n = len(done); pnl = sum(r["pnl"] for r in done); stake = sum(r["cost"] for r in done)
    print(f"simulated trades {len(rows)}, settled {n}, win rate {sum(r['won'] for r in done)/n:.0%}" if n else f"simulated trades {len(rows)}, settled 0")
    if n: print(f"pnl ${pnl:+.2f} on ${stake:.2f} staked ({pnl/stake:+.1%}); all costs (ask price + taker fee) included")
if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("cmd", choices=["run", "report"]); a.add_argument("--minutes", type=float, default=30)
    x = a.parse_args(); run(x.minutes) if x.cmd == "run" else report()
