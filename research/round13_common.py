"""Ledger entries and shared helpers for round 13 (research/r13-novel-ideas-2026-10-15.md)."""

from core.ledger import add_hypothesis
from research.round6_scan import lookup

MEMO = "research/r13-novel-ideas-2026-10-15.md"
HYPOTHESES_BEFORE = 125

# id, strategy file, one-line statement
RULES = [
    ("rev5sv_h3_band40_s", "short_horizon_v6.py", "Ranking only names with below-median short-sale volume share over the previous 5 sessions improves the 3-session band reversal rule"),
    ("rev5nn_h3_band40_s", "short_horizon_v6.py", "Ranking only names with no 8-K in the 5-day window improves the 3-session band reversal rule"),
    ("rev5wk_h3_band40_s", "short_horizon_v6.py", "Ranking only names with above-median Wikipedia attention improves the 3-session band reversal rule"),
    ("peer_fade_s", "round13_events.py", "Fading the move of same-industry peers that have not yet reported after a large earnings reaction earns >= 25 bps net per trade"),
    ("earn_premium_s", "round13_events.py", "Holding a member from 5 sessions before its earnings reaction to 1 session after earns >= 25 bps net per trade"),
    ("insider_cluster_s", "round13_events.py", "Buying after a second officer or director open-market purchase within 10 trading days earns >= 25 bps net per trade over 21 sessions"),
    ("spy_eod_flow_s", "round13_events.py", "Trading SPY in the direction of a >= 1% move from the previous close to 15:45, into the close, earns >= 2%/yr net"),
    ("weekday_seasonal_s", "round13_weekday.py", "Holding the top decile by mean same-weekday excess return of the last 20 weeks beats the equal-weight members net of 5 bps"),
]


def title_of(rule_id: str) -> str:
    return f"Novel ideas: {rule_id}"


def register(conn) -> dict:
    ids = lookup(conn)
    for rid, strategy, statement in RULES:
        if title_of(rid) not in ids:
            ids[title_of(rid)] = add_hypothesis(conn, title_of(rid), statement + f" (see {MEMO}); pre-registered bar and windows in the memo.",
                                                rationale="Round 13: novel ideas from the deep-research report of 2026-10-15.",
                                                research_memo=MEMO, strategy=strategy)
    return {rid: ids[title_of(rid)] for rid, _, _ in RULES}
