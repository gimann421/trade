"""Ledger entries and shared helpers for round 14 (research/r14-short-medium-ideas-2026-10-16.md)."""

import numpy as np
import pandas as pd

from core.ledger import add_hypothesis
from research.round6_scan import lookup

MEMO = "research/r14-short-medium-ideas-2026-10-16.md"
HYPOTHESES_BEFORE = 133

# id, strategy file, one-line statement
RULES = [
    ("rev5_h2_band_f45_s", "round14_fills.py", "Reading the 3:30 price and filling at 3:45 instead of at the close beats the same signal filled at the close by >= 1.0%/yr net (2-session band reversal rule)"),
    ("rev5_h3_band40_f45_s", "round14_fills.py", "Reading the 3:30 price and filling at 3:45 instead of at the close beats the same signal filled at the close by >= 1.0%/yr net (3-session band reversal rule)"),
    ("resmom_sttm_decile", "round14_momentum.py", "Adding last month's residual return for the top-turnover 30% of names to the residual momentum score beats the parent decile rule"),
    ("resmom_fip_decile", "round14_momentum.py", "Among the top 30% by residual momentum, holding the third with the smoothest path (lowest frog-in-the-pan measure) beats the parent decile rule"),
    ("announce_spy_s", "round14_announce.py", "Holding SPY only on FOMC statement days and employment-report days earns >= 8 bps per day net, above other days"),
]


def title_of(rule_id: str) -> str:
    return f"Round 14: {rule_id}"


def register(conn) -> dict:
    ids = lookup(conn)
    for rid, strategy, statement in RULES:
        if title_of(rid) not in ids:
            ids[title_of(rid)] = add_hypothesis(conn, title_of(rid), statement + f" (see {MEMO}); pre-registered bar and windows in the memo.",
                                                rationale="Round 14: ideas from the second deep-research report of 2026-10-15.",
                                                research_memo=MEMO, strategy=strategy)
    return {rid: ids[title_of(rid)] for rid, _, _ in RULES}


def block_bootstrap_positive(diff: pd.Series, block: int = 21, draws: int = 1000, seed: int = 0) -> float:
    """Share of block-bootstrap draws (blocks of `block` days) in which the mean of the daily series is above 0."""
    x = diff.dropna().to_numpy()
    n = len(x)
    if n < 2 * block:
        return float("nan")
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(draws, blocks))
    means = np.array([np.concatenate([x[s:s + block] for s in row])[:n].mean() for row in starts])
    return float((means > 0).mean())
