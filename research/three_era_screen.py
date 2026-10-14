"""Stage 1 and stage 2 of the funnel (see research/screen-funnel-2026-10-14.md).

    PYTHONPATH=. python research/three_era_screen.py

Stage 1: cells that pass the research bar in all three eras (2016-22, 2023+, 2000-15) go to the forward
record. The bar is the one already used in every round; nothing here changes it.
Stage 2: the chance the passers are luck. With N cells and per-era pass rates p1, p2, p3, a rule with no
edge in any era would pass all three in N*p1*p2*p3 cells on average. The expected share of fluke passers
(a false discovery rate for the group) is that expected count divided by the observed count, capped at 1.
ALERT is printed when it is 10% or lower. Output also goes to backtests/screen/three_era_screen.json.
"""

import json
import sys

from core.config import ROOT

ALERT_FDR = 0.10
ERAS = ("IS", "OOS", "OLD")
SUMMARY = ROOT / "backtests" / "old_era" / "old_era_summary.json"
OUT = ROOT / "backtests" / "screen" / "three_era_screen.json"


def screen(cells: list[dict]) -> dict:
    """cells: dicts with hypothesis, cell and one verdict per era (None when the era was not run)."""
    ok = lambda v: v == "supports"
    complete = [c for c in cells if all(c.get(e) is not None for e in ERAS)]
    n = len(complete)
    rates = {e: sum(ok(c[e]) for c in complete) / n if n else 0.0 for e in ERAS}
    passers = [(c["hypothesis"], c["cell"]) for c in complete if all(ok(c[e]) for e in ERAS)]
    expected = n * rates["IS"] * rates["OOS"] * rates["OLD"]
    fdr = min(1.0, expected / len(passers)) if passers else None
    return {"cells": n, "pass_rates": rates, "passers": passers, "expected_by_luck": expected,
            "fdr": fdr, "alert": fdr is not None and fdr <= ALERT_FDR}


def main() -> int:
    result = screen(json.loads(SUMMARY.read_text())["cells"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    rates = ", ".join(f"{e} {r:.0%}" for e, r in result["pass_rates"].items())
    print(f"{result['cells']} cells; pass rates {rates}")
    print(f"passing all three eras: {result['passers']}; expected by luck alone: {result['expected_by_luck']:.2f}")
    if result["fdr"] is None:
        print("no cell passes all three eras")
    else:
        print(f"expected share of flukes among the passers: {result['fdr']:.0%}")
    if result["alert"]:
        print(f"ALERT: false discovery rate {result['fdr']:.0%} is at or below {ALERT_FDR:.0%}: the passers are worth deeper work")
    return 0


if __name__ == "__main__":
    sys.exit(main())
