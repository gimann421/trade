"""Share of point-in-time S&P 500 members (2000-2015) that Yahoo can serve. Writes data/long/stock_coverage.json."""
import json, time, urllib.request
import pandas as pd
from core import universe as U
from core.data import DATA_DIR
print(U.fetch_membership())
m=U.load_membership()
me=pd.date_range("2000-01-31","2015-12-31",freq="ME")
mem=U.members_on(m,me)
tick=sorted(set().union(*mem)); print(len(m), m.index[0], len(tick))
out={}
UA={"User-Agent":"Mozilla/5.0"}
for i,t in enumerate(tick):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{t.replace('.','-')}?period1=946684800&period2=1451606400&interval=1d"
    try:
        r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30))
        res=r["chart"]["result"][0]; ts=res["timestamp"]
        out[t]=[ts[0],ts[-1],len(ts)]
    except Exception as e:
        out[t]=None
    time.sleep(0.25)
json.dump(out,open(str(DATA_DIR/'long'/'stock_coverage.json'),'w'))
print("done")
