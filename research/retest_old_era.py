"""Re-run the ETF-based ideas on 2000-2015 with their original rules (see research/r7-older-era-2026-10-14.md).

    PYTHONPATH=. python research/retest_old_era.py

The original round scripts run unchanged except for four redirections: the bar loader (Yahoo bars cut at
2015-12-31, BIL extended with the French T-bill series), the window (2000-01-01..2015-12-31, labelled "IS" so
the in-sample event minimums apply), the ledger writes (evidence rows are tagged and no status changes) and the
result files (written to backtests/old_era/, without equity curves). The 16 ETF rotation rules of the 2026-10-13 scan are re-run through
their own scorer the same way. Output: backtests/old_era/old_era_summary.json and a printed three-era table.
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from core import ledger
from core.config import ROOT
from core.ledger import connect
from core.longdata import OLD_END, old_bars
from core.portfolio import month_ends

OLD_START = "2000-01-01"
OLD_WINDOWS = {"IS": (OLD_START, OLD_END)}
TAG = "[2000-2015 retest; status unchanged] "
OUT = ROOT / "backtests" / "old_era"
GROUP = {1: range(2, 14), 2: range(14, 23), 3: range(23, 31), 4: (31, 32)}


def tagged_add_evidence(conn, hypothesis_id, kind, summary, verdict, ref=None):
    return ledger.add_evidence(conn, hypothesis_id, kind, TAG + summary, verdict, ref=ref)


def no_op(*args, **kwargs):
    return None


def light_save_result(result, strategy, symbol, backtests_dir=None, window=None):
    """The original save_result, into backtests/old_era/cells/ and without the large equity-curve file."""
    from core.backtest import save_result
    path = save_result(result, strategy, symbol, backtests_dir=OUT / "cells", window=window)
    path.with_name(path.stem + "_equity.csv").unlink(missing_ok=True)
    return path


@contextlib.contextmanager
def older_era(module):
    """Redirect a round script's data, windows, ledger writes and summary file."""
    redirects = {"WINDOWS": OLD_WINDOWS, "load_bars": old_bars, "add_evidence": tagged_add_evidence,
                 "set_status": no_op, "set_strategy": no_op, "save_result": light_save_result}
    saved = {name: getattr(module, name) for name in redirects if hasattr(module, name)}
    for name in saved:
        setattr(module, name, redirects[name])
    original_write = Path.write_text

    def write_text(self, data, *args, **kwargs):
        if self.name.endswith("_summary.json"):
            OUT.mkdir(parents=True, exist_ok=True)
            self = OUT / f"{self.stem}_old_era.json"
        return original_write(self, data, *args, **kwargs)

    try:
        with mock.patch.object(Path, "write_text", write_text):
            yield
    finally:
        for name, value in saved.items():
            setattr(module, name, value)


def run_round1(conn):
    from research import round1_verdicts as r1
    rows = {}
    with older_era(r1):
        bars = {s: old_bars(s) for s in r1.SYMBOLS}
        for hid in r1.HYPOTHESES:
            status, cells = r1.score(hid, conn, bars)
            rows[hid] = {"status": status, "cells": [{"symbol": c["symbol"], "window": "OLD", "verdict": c["verdict"],
                                                      "why": c["why"]} for c in cells]}
    return rows


def run_main(module, name):
    buffer = io.StringIO()
    with older_era(module), contextlib.redirect_stdout(buffer):
        module.main()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}_old_era.txt").write_text(buffer.getvalue())
    return json.loads((OUT / f"{name}_summary_old_era.json").read_text())


def cell_key(row):
    if "symbol" in row:
        return row["symbol"]
    if "universe" in row:
        return row["universe"]
    return row["cell"].rsplit(" ", 1)[0]


def collect(summary):
    """hypothesis id -> {status, cells: {key: {window: verdict}}} from a round summary JSON (rounds 2-4)."""
    out = {}
    for hid, h in summary.get("hypotheses", summary).items():
        out[int(hid)] = {"status": h["status"], "cells": {}}
        for row in h["cells"]:
            window = row.get("window") or row["cell"].rsplit(" ", 1)[1]
            out[int(hid)]["cells"].setdefault(cell_key(row), {})[window] = row["verdict"]
    return out


def earlier_verdicts(conn):
    """The original 2016-2026 verdicts per hypothesis and cell, from the stored summaries (rounds 2-4) and the
    ledger (round 1, which stored none)."""
    earlier = {}
    for n in (2, 3, 4):
        earlier.update(collect(json.loads((ROOT / "backtests" / f"round{n}_summary.json").read_text())))
    for hid in GROUP[1]:
        cells = {}
        for summary, verdict in conn.execute(
                "SELECT summary, verdict FROM evidence WHERE hypothesis_id = ? AND kind = 'backtest' AND summary NOT LIKE ? ORDER BY id",
                (hid, TAG + "%")):
            parts = summary.split()
            cells.setdefault(parts[1], {})[parts[2]] = verdict
        status = conn.execute("SELECT status FROM hypotheses WHERE id = ?", (hid,)).fetchone()[0]
        earlier[hid] = {"status": status, "cells": cells}
    return earlier


# --- the 16 ETF rotation rules --------------------------------------------------------------

def run_rotation(conn):
    from research import round6_scan as r6
    fs = r6.load_module("factor_scan_v1")
    names = sorted(set(fs.SECTORS) | set(fs.REGIONS) | {fs.CASH})
    frames = {s: old_bars(s)["close"] for s in names}
    index = frames["SPY"].index
    etf = pd.DataFrame({s: f for s, f in frames.items()}).reindex(index)
    decisions = index[month_ends(index)]
    ids = r6.lookup(conn)
    saved_windows, saved_first = r6.WINDOWS, fs.FIRST_DECISION
    r6.WINDOWS = OLD_WINDOWS
    results, cache = {}, {}
    try:
        for rule in [r for r in fs.RULES if r["family"] == "etf"]:
            tickers = rule["tickers"]
            first_valid = max(etf[t].first_valid_index() for t in tickers)
            ready = index[min(index.get_loc(first_valid) + 253, len(index) - 1)]
            first_decision = max(pd.Timestamp("1999-12-31"), decisions[decisions >= ready][0])
            fs.FIRST_DECISION = str(first_decision.date())
            close_raw = etf[list(tickers) + [fs.CASH]]
            scores = fs.score_matrix(rule["signal"], etf[tickers], None)
            scores[fs.CASH] = np.nan
            cells, _ = r6.score_rule(rule, fs, close_raw, scores, decisions, None, None, cache)
            c = cells["IS"]
            results[rule["id"]] = {"verdict": c["verdict"], "why": c["why"], "first_decision": fs.FIRST_DECISION,
                                   **{k: c[k] for k in ("rebalances", "net_active", "information_ratio", "placebo", "start", "end")}}
            summary = (f"factor_scan_v1 {rule['id']} 2000-2015 {c['start']}..{c['end']}, 5 bps: {c['rebalances']} rebalances, "
                       f"net active {c['net_active']:.2%}/yr, IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}. "
                       f"{c['verdict']}: {c['why']}")
            ledger.add_evidence(conn, ids[f"Scan v1: {rule['id']}"], "backtest", TAG + summary, c["verdict"])
    finally:
        r6.WINDOWS, fs.FIRST_DECISION = saved_windows, saved_first
    return results


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    conn = connect()
    earlier = earlier_verdicts(conn)
    old = {}
    old.update({hid: {"status": r["status"], "cells": {c["symbol"]: {"OLD": c["verdict"]} for c in r["cells"]}}
                for hid, r in run_round1(conn).items()})
    from research import round2_verdicts, round3_verdicts, round4_verdicts
    for n, module in ((2, round2_verdicts), (3, round3_verdicts), (4, round4_verdicts)):
        summary = run_main(module, f"round{n}")
        old.update(collect(summary))
    rotation = run_rotation(conn)
    conn.close()

    table = []
    for hid in sorted(old):
        for key, windows in old[hid]["cells"].items():
            before = earlier.get(hid, {"cells": {}})["cells"].get(key, {})
            table.append({"hypothesis": hid, "cell": key, "IS": before.get("IS"), "OOS": before.get("OOS"),
                          "OLD": windows.get("OLD", windows.get("IS"))})
    summary = {"old_status": {h: old[h]["status"] for h in old},
               "earlier_status": {h: earlier[h]["status"] for h in old if h in earlier},
               "cells": table, "rotation": rotation}
    (OUT / "old_era_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")

    sup = lambda v: v == "supports"
    print(f"{len(table)} cells run; {sum(sup(t['OLD']) for t in table)} pass in 2000-2015")
    print("cells passing in 2000-2015 and both earlier windows:",
          [(t["hypothesis"], t["cell"]) for t in table if sup(t["OLD"]) and sup(t["IS"]) and sup(t["OOS"])])
    print("cells passing 2000-2015 and at least one earlier window:",
          [(t["hypothesis"], t["cell"], t["IS"], t["OOS"]) for t in table if sup(t["OLD"]) and (sup(t["IS"]) or sup(t["OOS"]))])
    print("hypotheses whose script status on 2000-2015 is supported:", [h for h in old if old[h]["status"] == "supported"])
    print("rotation rules passing 2000-2015:", [k for k, v in rotation.items() if sup(v["verdict"])], f"of {len(rotation)}")


if __name__ == "__main__":
    sys.exit(main())
