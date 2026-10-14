"""Post-hoc check for round 9: the supported rule's close-timed version on the member tickers NOT in the 300-name sample.

    PYTHONPATH=. python research/round9_holdout.py
Close-timed (same-day close signal and fill), so it cannot be traded; it only asks whether the band cut turnover and kept
the edge on stocks the round never looked at. Report-only, not a ledger test."""
import numpy as np
import pandas as pd
from core.data import load_bars
from core.intraday import sample_tickers
from core.portfolio import month_ends, simulate
from core.universe import FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on, month_end_members
from research.round5_verdicts import window_stats
from research.round6_scan import load_module
from research.round8_short_horizon import COSTS, WINDOWS, cleaned, dirty_index

fs, sh = load_module("factor_scan_v1"), load_module("short_horizon_v2")
membership = load_membership()
sample = set(sample_tickers())
wanted = sorted(t for t in month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END) if t not in sample)
index = load_bars("VTI").index
close = load_member_panel(wanted, "close").reindex(index)
open_ = load_member_panel(wanted, "open").reindex(index)
full = close.copy(); full["BIL"] = load_bars("BIL")["close"].reindex(index)
ff, dirty = full.ffill(), dirty_index(index)
fs.FIRST_DECISION = sh.FIRST_DECISION
probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
_, bt, bd = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, full.columns), index[month_ends(index)], membership, None)
bench = {k: cleaned(simulate(ff, bt, b), dirty) for k, b in COSTS.items()}
first = index[index.get_loc(bd[0]["date"]) + 1]
fn = lambda d: members_on(membership, d)
print(len(wanted), "holdout tickers")
for rid in ("rev5_h2_s", "rev5_h2_band_s", "id5_h2_band_s"):
    rule = next(r for r in sh.RULES if r["id"] == rid)
    sc = sh.score_matrix(rule["signal"], open_, close, None); sc["BIL"] = np.nan
    t, _ = sh.generate_targets(rule, full, sc, None, sh.decision_dates(index, rule["hold"]), fn)
    out = []
    for lab, (s, e) in WINDOWS.items():
        a = window_stats(cleaned(simulate(ff, t, 5.0), dirty), bench["primary"], first, s, e)[2]
        b = window_stats(cleaned(simulate(ff, t, 10.0), dirty), bench["stress"], first, s, e)[2]
        late = window_stats(cleaned(simulate(ff, t.shift(1), 5.0), dirty), cleaned(simulate(ff, bt.shift(1), 5.0), dirty), first, s, e)[2]
        out.append(f"{lab} net {a['net_active']:+.1%} IR {a['information_ratio']:+.2f} turn {a['annual_turnover']:.0f} 10bp {b['net_active']:+.1%} late {late['net_active']:+.1%}")
    print(rid.replace("_s", "") + " (close-timed): " + " | ".join(out))
