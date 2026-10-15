"""Score hypotheses 129-132 of research/r13-novel-ideas-2026-10-15.md (event rules: peer fade, hold into earnings,
insider cluster buys, SPY end-of-day flow).

    PYTHONPATH=. python research/round13_events.py --run
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import DATA_DIR, load_bars
from core.edgar import load_constituents, load_events, reaction_sessions
from core.industry import load_sic
from core.ledger import add_evidence, connect, set_status, set_strategy
from core.universe import STOCK_DIR, load_member_panel, load_membership, members_on
from research.round13_common import register, title_of
from research.round6_scan import lookup

OUT_DIR = ROOT / "backtests" / "round13_events"
INSIDER_PATH = DATA_DIR / "insider" / "purchases.csv"
SPY_PATH = DATA_DIR / "spy_snapshots.csv"
WINDOWS = {"IS": ("2017-01-01", "2022-12-31"), "OOS": ("2023-01-01", "2100-01-01")}
DIRTY = (pd.Timestamp("2020-03-09"), pd.Timestamp("2020-03-20"))
COST_BPS, STRESS_BPS = 5.0, 10.0
BAR_PER_TRADE, BAR_T, BAR_PLACEBO = 25.0, 2.0, 0.95
N_PLACEBO, SEED = 1000, 0
MIN_TRADES = {"peer_fade_s": (150, 100), "earn_premium_s": (150, 100), "insider_cluster_s": (40, 20), "spy_eod_flow_s": (100, 60)}


class Panel:
    """Close prices of every loaded name, point-in-time membership, and the equal-weight member benchmark."""

    def __init__(self):
        membership = load_membership()
        tickers = sorted({p.name.rsplit("_1Day", 1)[0] for p in STOCK_DIR.glob("*_1Day.csv")})
        self.index = load_bars("VTI").index
        close = load_member_panel(tickers, "close").reindex(self.index)
        self.close = close
        self.logc = np.log(close.to_numpy(dtype=float))
        self.cols = list(close.columns)
        self.col_pos = {c: k for k, c in enumerate(self.cols)}
        member = np.zeros(close.shape, dtype=bool)
        for t, names in enumerate(members_on(membership, self.index)):
            member[t, [self.col_pos[n] for n in names if n in self.col_pos]] = True
        self.member = member
        self._d, self._bm = {}, {}

    def D(self, h):
        """Log return from session t to t+h, NaN where either close is missing or t+h is past the end."""
        if h not in self._d:
            d = np.full_like(self.logc, np.nan)
            d[:-h] = self.logc[h:] - self.logc[:-h]
            self._d[h] = d
        return self._d[h]

    def BM(self, h):
        if h not in self._bm:
            d = self.D(h)
            ok = self.member & np.isfinite(d)
            s = np.where(ok, d, 0.0).sum(axis=1)
            n = ok.sum(axis=1)
            self._bm[h] = np.where(n > 0, s / np.maximum(n, 1), np.nan)
        return self._bm[h]

    def pos(self, date) -> int:
        """Position of the first session on or after `date`."""
        return int(self.index.searchsorted(pd.Timestamp(date)))


def trade_table(panel: Panel, rows: list[dict]) -> pd.DataFrame:
    """rows: ticker, entry (position), hold (sessions), sign. Adds entry date and gross signed abnormal log return."""
    frame = pd.DataFrame(rows)
    frame = frame[frame["ticker"].isin(panel.col_pos)].copy()
    frame["exit"] = frame["entry"] + frame["hold"]
    frame = frame[(frame["entry"] >= 0) & (frame["exit"] < len(panel.index)) & (frame["hold"] >= 1)]
    gross = []
    for t, h, i, sgn in zip(frame["entry"], frame["hold"], frame["ticker"].map(panel.col_pos), frame["sign"]):
        gross.append(sgn * (panel.D(h)[t, i] - panel.BM(h)[t]))
    frame["gross"] = gross
    frame = frame[np.isfinite(frame["gross"])]
    frame["date"] = panel.index[frame["entry"].to_numpy()]
    frame["exit_date"] = panel.index[frame["exit"].to_numpy()]
    touch = (frame["date"] <= DIRTY[1]) & (frame["exit_date"] >= DIRTY[0])
    return frame[~touch].reset_index(drop=True)


def cluster_t(x: np.ndarray, weeks: np.ndarray) -> float:
    n = len(x)
    if n < 3:
        return float("nan")
    m = x.mean()
    e = x - m
    g = pd.Series(e).groupby(weeks).sum()
    se = np.sqrt((g ** 2).sum()) / n
    return float(m / se) if se > 0 else float("nan")


def placebo_percentile(panel: Panel, sub: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp, actual_mean: float, cost: float) -> float:
    """Percentile of the actual mean net per trade among random same-size sets of trades (random session in the window,
    random member, the trade's own hold and sign)."""
    rng = np.random.default_rng(SEED)
    window = np.flatnonzero((panel.index >= lo) & (panel.index <= hi))
    sums = np.zeros(N_PLACEBO)
    for h, grp in sub.groupby("hold"):
        d, bm = panel.D(int(h)), panel.BM(int(h))
        signs = grp["sign"].to_numpy()
        m = len(grp)
        t = rng.choice(window, size=(m, N_PLACEBO))
        i = rng.integers(0, len(panel.cols), size=(m, N_PLACEBO))
        for _ in range(60):
            bad = ~(panel.member[t, i] & np.isfinite(d[t, i]) & np.isfinite(bm[t]))
            if not bad.any():
                break
            t[bad] = rng.choice(window, size=int(bad.sum()))
            i[bad] = rng.integers(0, len(panel.cols), size=int(bad.sum()))
        ar = signs[:, None] * (d[t, i] - bm[t])
        sums += np.nan_to_num(ar, nan=0.0).sum(axis=0) - cost * m
    means = sums / len(sub)
    return float((means < actual_mean).mean())


def score(panel: Panel, rid: str, trades: pd.DataFrame, annualise: bool = False) -> dict:
    cells = {}
    for label, (a, b) in WINDOWS.items():
        lo, hi = pd.Timestamp(a), pd.Timestamp(b)
        sub = trades[(trades["date"] >= lo) & (trades["date"] <= hi)]
        n = len(sub)
        minimum = MIN_TRADES[rid][0 if label == "IS" else 1]
        cell = {"trades": n}
        if n:
            gross = sub["gross"].to_numpy()
            c1, c2 = 2 * COST_BPS / 1e4, 2 * STRESS_BPS / 1e4
            net = gross - c1
            weeks = sub["date"].dt.strftime("%G-%V").to_numpy()
            years = max((min(hi, panel.index[-1]) - max(lo, panel.index[0])).days / 365.25, 1e-9)
            cell.update({"gross_bps": float(gross.mean() * 1e4), "net_bps": float(net.mean() * 1e4), "stress_bps": float((gross - c2).mean() * 1e4),
                         "t": cluster_t(net, weeks), "trades_per_year": n / years, "hit_rate": float((net > 0).mean())})
            cell["annual_net"] = cell["net_bps"] / 1e4 * cell["trades_per_year"]
            cell["placebo"] = placebo_percentile(panel, sub, lo, min(hi, panel.index[-1]), float(net.mean()), c1) if n >= 5 else float("nan")
        fails = []
        if n < minimum:
            verdict, fails = "inconclusive", [f"only {n} trades (need {minimum})"]
        else:
            if annualise:
                if cell["annual_net"] < 0.02:
                    fails.append(f"annual net {cell['annual_net']:.2%} < 2%")
            elif cell["net_bps"] < BAR_PER_TRADE:
                fails.append(f"net {cell['net_bps']:.1f} bps per trade < {BAR_PER_TRADE:.0f}")
            if not cell["t"] >= BAR_T:
                fails.append(f"t {cell['t']:.2f} < {BAR_T}")
            if not cell["placebo"] >= BAR_PLACEBO:
                fails.append(f"placebo {cell['placebo']:.3f} < {BAR_PLACEBO}")
            if cell["stress_bps"] <= 0:
                fails.append(f"10 bps per side net {cell['stress_bps']:.1f} bps not above 0")
            verdict = "contradicts" if fails else "supports"
            if not fails:
                fails = ["passes the bar and the stress check"]
        cell.update({"verdict": verdict, "why": fails})
        cells[label] = cell
    return cells


def fmt(rid, cells, tag=""):
    return f"{rid:20s}{tag:14s}" + "  ".join(
        f"{w}: n {c['trades']:5d} gross {c.get('gross_bps', float('nan')):+7.1f} net {c.get('net_bps', float('nan')):+7.1f} bps "
        f"t {c.get('t', float('nan')):+5.2f} pl {c.get('placebo', float('nan')):.2f} 10bp {c.get('stress_bps', float('nan')):+7.1f} "
        f"yr {c.get('annual_net', float('nan')):+6.2%}" for w, c in cells.items()) + "  -> " + "/".join(c["verdict"] for c in cells.values())


# --- event builders -------------------------------------------------------------------------------------------------

def earnings_sessions(panel: Panel) -> pd.DataFrame:
    ev = load_events()
    ev["session"] = reaction_sessions(ev["acceptance_utc"], panel.index)
    ev = ev.dropna(subset=["session"])
    ev["pos"] = panel.index.get_indexer(pd.DatetimeIndex(ev["session"]))
    return ev[["symbol", "session", "pos"]].drop_duplicates(["symbol", "pos"]).sort_values(["symbol", "pos"]).reset_index(drop=True)


def build_peer_fade(panel: Panel, ev: pd.DataFrame, alt_exit: bool = False) -> pd.DataFrame:
    sic = load_sic()
    groups = sic.groupby(sic).filter(lambda s: len(s) >= 5)
    members = groups.groupby(groups).groups                                   # sic2 -> symbols
    by_symbol = {s: g["pos"].to_numpy() for s, g in ev.groupby("symbol")}
    date_of = lambda pos: panel.index[pos]
    rows = []
    for _, r in ev.iterrows():
        R, s = r["symbol"], int(r["pos"])
        if R not in panel.col_pos or R not in groups.index or s < 1:
            continue
        i = panel.col_pos[R]
        ar = panel.logc[s, i] - panel.logc[s - 1, i] - panel.BM(1)[s - 1]
        if not np.isfinite(ar) or abs(ar) < 0.05:
            continue
        sd = date_of(s)
        for peer in members[groups[R]]:
            if peer == R or peer not in by_symbol or peer not in panel.col_pos:
                continue
            q = by_symbol[peer]
            if ((q > s - 40) & (q <= s)).any():
                continue                                                         # (a) already reported this quarter
            expected = None
            for pos in q:
                days = (sd - date_of(pos)).days
                if 330 <= days <= 400:
                    e = panel.pos(date_of(pos) + pd.Timedelta(days=364))
                    if 2 <= e - s <= 30:
                        expected = e if expected is None else min(expected, e)
            if expected is None:
                continue
            entry, exit_ = s + 1, expected - 1
            if exit_ <= entry:
                continue
            hold = min(10, exit_ - entry) if alt_exit else exit_ - entry
            rows.append({"ticker": peer, "entry": entry, "hold": hold, "sign": -float(np.sign(ar)), "reporter": R, "leg": "good" if ar > 0 else "bad"})
    return trade_table(panel, rows)


def build_earn_premium(panel: Panel, ev: pd.DataFrame) -> pd.DataFrame:
    rows = [{"ticker": r.symbol, "entry": int(r.pos) - 5, "hold": 6, "sign": 1.0} for r in ev.itertuples()]
    return trade_table(panel, rows)


def build_insider(panel: Panel) -> pd.DataFrame:
    raw = pd.read_csv(INSIDER_PATH, dtype=str)
    rel = raw["RPTOWNER_RELATIONSHIP"].fillna("")
    raw = raw[rel.str.contains("Officer|Director", case=False)]
    raw["value"] = pd.to_numeric(raw["TRANS_SHARES"], errors="coerce") * pd.to_numeric(raw["TRANS_PRICEPERSHARE"], errors="coerce")
    raw = raw[raw["value"] >= 25_000]
    raw["filed"] = pd.to_datetime(raw["FILING_DATE"], format="%d-%b-%Y", errors="coerce")
    raw = raw.dropna(subset=["filed"])
    cik_to_symbol = {str(int(c)): s for s, c in load_constituents().items()}
    raw["symbol"] = raw["ISSUERCIK"].astype(str).str.lstrip("0").map(cik_to_symbol)
    raw = raw.dropna(subset=["symbol"])
    raw["fpos"] = [panel.pos(d) for d in raw["filed"]]
    rows = []
    for symbol, g in raw.groupby("symbol"):
        g = g.sort_values("fpos")
        last_entry = -10**9
        for k in range(len(g)):
            window = g[(g["fpos"] <= g.iloc[k]["fpos"]) & (g["fpos"] > g.iloc[k]["fpos"] - 10)]
            if window["RPTOWNERCIK"].nunique() >= 2 and g.iloc[k]["fpos"] + 1 >= last_entry + 60:
                entry = int(g.iloc[k]["fpos"]) + 1
                rows.append({"ticker": symbol, "entry": entry, "hold": 21, "sign": 1.0})
                last_entry = entry
    return trade_table(panel, rows)


def build_spy(panel: Panel):
    snap = pd.read_csv(SPY_PATH, index_col=0, parse_dates=True).dropna()
    r = snap["p1545"] / snap["close"].shift(1) - 1
    day = snap["close"] / snap["p1545"] - 1
    pick = r.abs() >= 0.01
    gross = (np.sign(r) * day)[pick]
    frame = pd.DataFrame({"date": gross.index, "gross": gross.to_numpy(), "sign": np.sign(r[pick]).to_numpy()})
    return frame[(frame["date"] < DIRTY[0]) | (frame["date"] > DIRTY[1])].reset_index(drop=True)


def score_spy(snap_trades: pd.DataFrame, snap: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    day = (snap["close"] / snap["p1545"] - 1).dropna()
    cells = {}
    for label, (a, b) in WINDOWS.items():
        lo, hi = pd.Timestamp(a), pd.Timestamp(b)
        sub = snap_trades[(snap_trades["date"] >= lo) & (snap_trades["date"] <= hi)]
        n = len(sub)
        cell = {"trades": n}
        fails = []
        if n:
            c1, c2 = 2 * COST_BPS / 1e4, 2 * STRESS_BPS / 1e4
            net = sub["gross"].to_numpy() - c1
            years = max((min(hi, snap.index[-1]) - max(lo, snap.index[0])).days / 365.25, 1e-9)
            pool = day[(day.index >= lo) & (day.index <= hi) & ~((day.index >= DIRTY[0]) & (day.index <= DIRTY[1]))].to_numpy()
            signs = sub["sign"].to_numpy()
            draws = rng.choice(pool, size=(N_PLACEBO, n)) * rng.permuted(np.tile(signs, (N_PLACEBO, 1)), axis=1)
            placebo_means = (draws - c1).mean(axis=1)
            cell.update({"gross_bps": float(sub["gross"].mean() * 1e4), "net_bps": float(net.mean() * 1e4),
                         "stress_bps": float((sub["gross"] - c2).mean() * 1e4), "trades_per_year": n / years,
                         "t": cluster_t(net, sub["date"].dt.strftime("%G-%V").to_numpy()),
                         "placebo": float((placebo_means < net.mean()).mean())})
            cell["annual_net"] = cell["net_bps"] / 1e4 * cell["trades_per_year"]
        minimum = MIN_TRADES["spy_eod_flow_s"][0 if label == "IS" else 1]
        if n < minimum:
            verdict, fails = "inconclusive", [f"only {n} trades (need {minimum})"]
        else:
            if cell["annual_net"] < 0.02:
                fails.append(f"annual net {cell['annual_net']:.2%} < 2%")
            if not cell["t"] >= BAR_T:
                fails.append(f"t {cell['t']:.2f} < {BAR_T}")
            if not cell["placebo"] >= BAR_PLACEBO:
                fails.append(f"placebo {cell['placebo']:.3f} < {BAR_PLACEBO}")
            if cell["stress_bps"] <= 0:
                fails.append(f"10 bps per side net {cell['stress_bps']:.1f} bps not above 0")
            verdict = "contradicts" if fails else "supports"
            fails = fails or ["passes the bar and the stress check"]
        cell.update({"verdict": verdict, "why": fails})
        cells[label] = cell
    return cells


def run(only=None):
    panel = Panel()
    ev = earnings_sessions(panel)
    print(f"panel {len(panel.cols)} names, {len(panel.index)} sessions; {len(ev)} earnings reaction sessions, {ev['symbol'].nunique()} symbols", flush=True)
    results, diagnostics = {}, {}

    if only != "spy":
        peer = build_peer_fade(panel, ev)
        results["peer_fade_s"] = {"cells": score(panel, "peer_fade_s", peer), "n_pairs": len(peer), "mean_hold": float(peer["hold"].mean()) if len(peer) else None}
        print(fmt("peer_fade_s", results["peer_fade_s"]["cells"]), flush=True)
        diagnostics = {}
        for leg in ("good", "bad"):
            sub = peer[peer["leg"] == leg] if len(peer) else peer
            diagnostics[f"peer_fade_{leg}"] = score(panel, "peer_fade_s", sub)
            print(fmt("  report only", diagnostics[f"peer_fade_{leg}"], f" {leg}-news"), flush=True)
        alt = build_peer_fade(panel, ev, alt_exit=True)
        diagnostics["peer_fade_10"] = score(panel, "peer_fade_s", alt)
        print(fmt("  report only", diagnostics["peer_fade_10"], " exit<=10"), flush=True)

        earn = build_earn_premium(panel, ev)
        results["earn_premium_s"] = {"cells": score(panel, "earn_premium_s", earn)}
        print(fmt("earn_premium_s", results["earn_premium_s"]["cells"]), flush=True)

        ins = build_insider(panel)
        results["insider_cluster_s"] = {"cells": score(panel, "insider_cluster_s", ins)}
        print(fmt("insider_cluster_s", results["insider_cluster_s"]["cells"]), flush=True)

    if SPY_PATH.exists():
        spy_snap = pd.read_csv(SPY_PATH, index_col=0, parse_dates=True).dropna()
        results["spy_eod_flow_s"] = {"cells": score_spy(build_spy(panel), spy_snap)}
        print(fmt("spy_eod_flow_s", results["spy_eod_flow_s"]["cells"]), flush=True)
    else:
        print("SPY snapshots not downloaded yet; spy_eod_flow_s not run", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"round13_events_{stamp}.json"
    conn = connect()
    register(conn)
    ids = lookup(conn)
    for rid, res in results.items():
        hid = ids[title_of(rid)]
        for w, c in res["cells"].items():
            summary = (f"{rid} {w}: {c['trades']} trades, mean net {c.get('net_bps', float('nan')):.1f} bps per trade (gross {c.get('gross_bps', float('nan')):.1f}), "
                       f"cluster t {c.get('t', float('nan')):.2f}, placebo {c.get('placebo', float('nan')):.3f}, 10 bps per side {c.get('stress_bps', float('nan')):.1f} bps, "
                       f"annualised {c.get('annual_net', float('nan')):.2%}. {c['verdict']}: {'; '.join(c['why'])}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
        verdicts = [c["verdict"] for c in res["cells"].values()]
        status = "supported" if all(v == "supports" for v in verdicts) else "rejected" if "contradicts" in verdicts else "testing"
        set_strategy(conn, hid, "round13_events.py")
        set_status(conn, hid, status)
        print(f"{rid}: {status}")
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "bar": {"per_trade_bps": BAR_PER_TRADE, "t": BAR_T, "placebo": BAR_PLACEBO},
                                "results": results, "diagnostics": diagnostics}, indent=1, default=str) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--only", choices=["spy"], help="run only the SPY rule (its data arrived after the first run)")
    args = parser.parse_args()
    if args.run:
        run(args.only)


if __name__ == "__main__":
    sys.exit(main())
