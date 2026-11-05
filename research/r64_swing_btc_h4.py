"""Pre-registered H4 swing rules on BTC-USD (Coinbase hourly -> 4h). 3 rules, long/flat and long/short.
Cost 10 bps per side (taker+slippage). Eras: IS 2016-2021, OOS 2022+. Placebo: random-timed same-exposure.
"""
import time, json, urllib.request, numpy as np, pandas as pd, concurrent.futures as cf, sys
def get(u):
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"r"}),timeout=30))
        except Exception: time.sleep(1+i)
iso=lambda x: time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(x))
s0=int(pd.Timestamp("2016-01-01",tz="UTC").timestamp()); e0=int(time.time())//3600*3600
chunks=[(t,min(t+299*3600,e0)) for t in range(s0,e0,299*3600)]
def f(c):
    d=get(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600&start={iso(c[0])}&end={iso(c[1])}"); return d or []
rows=[]
with cf.ThreadPoolExecutor(4) as ex:
    for d in ex.map(f,chunks): rows+=d
df=pd.DataFrame(rows,columns="t l h o c v".split()).drop_duplicates("t").sort_values("t")
df.index=pd.to_datetime(df.t,unit="s"); print("hourly bars",len(df),df.index[0],df.index[-1])
df.to_pickle("/tmp/btc_h1.pkl")
h4=df.resample("4h").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
c=h4.c; ret=c.pct_change()
def sig_donch(n):
    up=c>c.shift(1).rolling(n).max(); dn=c<c.shift(1).rolling(n).min()
    s=pd.Series(np.nan,index=c.index); s[up]=1; s[dn]=0; return s.ffill().fillna(0)
def sig_sma(a,b): return (c.rolling(a).mean()>c.rolling(b).mean()).astype(float)
def sig_rsi():
    d=c.diff(); up=d.clip(lower=0).rolling(14).mean(); dn=(-d.clip(upper=0)).rolling(14).mean(); rsi=100-100/(1+up/dn)
    trend=c>c.rolling(200).mean(); s=pd.Series(np.nan,index=c.index); s[(rsi<35)&trend]=1; s[(rsi>60)|(~trend)]=0; return s.ffill().fillna(0)
rules={"donchian55":sig_donch(55),"sma50_200":sig_sma(50,200),"rsi_pullback_in_uptrend":sig_rsi()}
cost=0.001
def stats(pos,r):
    p=pos.shift(1).fillna(0); net=p*r-p.diff().abs().fillna(0)*cost
    return net
bh=ret
def summ(net,mask):
    x=net[mask].dropna(); b=bh[mask].dropna()
    ann=lambda z: z.mean()*6*365
    return f"ann {ann(x):+.1%} sharpe {x.mean()/x.std()*np.sqrt(6*365):+.2f} (buyhold ann {ann(b):+.1%} sh {b.mean()/b.std()*np.sqrt(6*365):+.2f}) exposure {(x!=0).mean():.0%}"
IS=c.index<"2022-01-01"; OOS=~IS
rng=np.random.default_rng(1)
for k,s in rules.items():
    net=stats(s,ret); print(k,"| IS",summ(net,IS),"| OOS",summ(net,OOS))
    # placebo: shuffle block-wise the position series (same exposure, random timing); 500 draws, Sharpe vs actual full sample
    act=net.dropna(); sh=act.mean()/act.std()
    blocks=np.array_split(s.values,len(s)//30); out=[]
    for _ in range(500):
        idx=rng.permutation(len(blocks)); ps=pd.Series(np.concatenate([blocks[i] for i in idx]),index=c.index[:sum(len(b) for b in blocks)])
        n2=stats(ps,ret.loc[ps.index]).dropna(); out.append(n2.mean()/n2.std())
    print("   placebo p(sharpe>=actual)",np.mean(np.array(out)>=sh))
