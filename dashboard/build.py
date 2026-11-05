"""Build the live status dashboard (dashboard/index.html). Read-only: no orders, no secrets printed or embedded.
Usage: python dashboard/build.py [--out dashboard/index.html]
Sources: origin/paper-log (nav, status, decisions, journal), Alpaca PAPER account (read only), memory/ledger.db,
research/ memos, setups/, and dashboard/live.json (routines + threads, written by the refresh routine from the
platform tools, which a plain script cannot reach)."""
import csv, io, json, os, re, sqlite3, subprocess, sys, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "dashboard", "index.html")

def git(*a):
    r = subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None

def show(ref, path):
    return git("show", f"{ref}:{path}")

LOG = "origin/paper-log" if git("rev-parse", "--verify", "origin/paper-log") else "HEAD"

def jload(s):
    try: return json.loads(s) if s else None
    except Exception: return None

# ---- rules (shadow records + paper slices)
tracked = (jload(show(LOG, "paper/tracked.json")) or jload(open(os.path.join(ROOT, "paper/tracked.json")).read()) or {}).get("tracked", [])
rules = []
for t in tracked:
    name = t["rule"]
    st = jload(show(LOG, f"paper/{name}/status.json")) or {}
    nav = []
    raw = show(LOG, f"paper/{name}/nav.csv")
    if raw:
        seen = {}
        for r in csv.DictReader(io.StringIO(raw)):
            seen[r["date"]] = [r["date"], round(float(r["nav"]), 2), round(float(r["benchmark_nav"]), 2)]
        nav = list(seen.values())
    rules.append(dict(rule=name, kind=t.get("kind", "stock"), start=t.get("start"), alloc=t.get("allocation_pct", 0),
        state=st.get("state", "running" if nav else "waiting"), asof=st.get("asof"), nav=nav,
        total_return=st.get("total_return"), excess=st.get("excess_return"), decisions=st.get("decisions"),
        first_decision=st.get("first_decision"), last_decision=st.get("last_decision"), holdings=len(st.get("holdings") or []),
        in_position=st.get("in_position"), caveat=st.get("caveat"), note=t.get("pick_note")))

# ---- journal: orders per day per strategy
journal = {}
ls = git("ls-tree", "--name-only", LOG, "journal/") or ""
for p in sorted(ls.split())[-6:]:
    day = os.path.basename(p).replace(".jsonl", "")
    for l in (show(LOG, p) or "").splitlines():
        d = jload(l)
        if d: journal.setdefault(day, {}).setdefault(d.get("strategy") or "other", {}).setdefault(d.get("action"), 0)
        if d: journal[day][d.get("strategy") or "other"][d.get("action")] += 1

# ---- Alpaca paper account (read only)
acct = dict(ok=False)
try:
    sys.path.insert(0, ROOT)
    from core.broker import get_paper_client
    from alpaca.trading.requests import GetPortfolioHistoryRequest, GetOrdersRequest
    c = get_paper_client(); a = c.get_account()
    h = c.get_portfolio_history(GetPortfolioHistoryRequest(period="1M", timeframe="1D"))
    pos = c.get_all_positions()
    opn = c.get_orders(GetOrdersRequest(status="open", limit=500))
    recent = c.get_orders(GetOrdersRequest(status="all", limit=500))
    eq = float(a.equity)
    acct = dict(ok=True, status=str(a.status.value if hasattr(a.status, "value") else a.status), equity=eq,
        last_equity=float(a.last_equity), cash=float(a.cash), buying_power=float(a.buying_power),
        history=[[dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), round(e, 2)] for t, e in zip(h.timestamp, h.equity) if e],
        positions=sorted([dict(s=p.symbol, mv=round(float(p.market_value), 2), pl=round(float(p.unrealized_pl), 2)) for p in pos], key=lambda x: -abs(x["mv"])),
        gross=round(sum(abs(float(p.market_value)) for p in pos) / eq * 100, 1) if eq else None,
        open_orders=len(opn))
    by = {}
    for o in recent:
        k = (o.client_order_id or "").split("__")[0] or "manual"
        d = o.created_at.strftime("%Y-%m-%d"); st = str(getattr(o.status, "value", o.status))
        by.setdefault(d, {}).setdefault(k, {}).setdefault(st, 0); by[d][k][st] += 1
    acct["orders_by_day"] = {d: by[d] for d in sorted(by)[-5:]}
except Exception as e:
    acct["error"] = type(e).__name__

# ---- rule search ledger
search = dict(total=0, by_status={}, supported=[], rounds=[])
try:
    db = sqlite3.connect(os.path.join(ROOT, "memory", "ledger.db"))
    search["by_status"] = dict(db.execute("select status,count(*) from hypotheses group by 1").fetchall())
    search["total"] = sum(search["by_status"].values())
    search["supported"] = [dict(id=i, title=t, status=s) for i, t, s in db.execute(
        "select id,title,status from hypotheses where status in ('supported','testing') order by id desc limit 30")]
    search["recent"] = [dict(id=i, title=t, status=s, at=u[:10]) for i, t, s, u in db.execute(
        "select id,title,status,updated_at from hypotheses order by id desc limit 12")]
    search["per_day"] = [list(r) for r in db.execute("select substr(created_at,1,10),count(*) from hypotheses group by 1 order by 1")]
except Exception as e:
    search["error"] = type(e).__name__
for f in sorted(os.listdir(os.path.join(ROOT, "research")))[-400:]:
    m = re.match(r"(r\d+)-.*\.md$", f)
    if m:
        first = open(os.path.join(ROOT, "research", f), errors="ignore").readline().strip("# \n")
        search["rounds"].append(dict(id=m.group(1), file=f, title=first))
search["rounds"] = sorted(search["rounds"], key=lambda r: int(r["id"][1:]))[-8:]

# ---- simulated setups
setups = dict(swing=None, poly=None)
sw = show("origin/setups-swing-state", "setups/swing_h4/state.json") or show("HEAD", "setups/swing_h4/state.json")
setups["swing"] = jload(sw)
pp = os.path.join(ROOT, "setups", "polymarket_lag", "data", "sim_trades.jsonl")
if os.path.exists(pp):
    rows = [jload(l) for l in open(pp) if l.strip()]
    rows = [r for r in rows if r]
    done = [r for r in rows if r.get("pnl") is not None]
    setups["poly"] = dict(trades=len(rows), settled=len(done), pnl=round(sum(r["pnl"] for r in done), 2),
        wins=sum(1 for r in done if r.get("won")), curve=[round(x, 2) for x in __import__("itertools").accumulate(r["pnl"] for r in done)])

live = jload(open(os.path.join(ROOT, "dashboard", "live.json")).read()) if os.path.exists(os.path.join(ROOT, "dashboard", "live.json")) else {}
data = dict(built=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), rules=rules, journal=journal, account=acct,
    search=search, setups=setups, live=live or {})
tpl = open(os.path.join(ROOT, "dashboard", "template.html")).read()
open(OUT, "w").write(tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))))
print("wrote", OUT, len(open(OUT).read()) // 1024, "KB; account ok:", acct["ok"], "rules:", len(rules))
