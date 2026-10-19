"""Ledger entries and shared helpers for round 15 (research/r15-conditioned-reversal-2026-10-17.md)."""

from core.ledger import add_hypothesis
from research.round6_scan import lookup

MEMO = "research/r15-conditioned-reversal-2026-10-17.md"
HYPOTHESES_BEFORE = 138

# id, filter, one-line statement
RULES = [
    ("rev5hi_h3_band40_s", "F1", "Ranking only names far from their 52-week high (below the median ratio) improves the 3-session band reversal rule"),
    ("rev5lm_h3_band40_s", "F2", "Ranking only medium-term losers (12-1 month return below the median) improves the 3-session band reversal rule"),
    ("rev5lv_h3_band40_s", "F3", "Ranking only low-volatility names (60-day volatility below the median) improves the 3-session band reversal rule"),
]


def title_of(rule_id: str) -> str:
    return f"Round 15: {rule_id}"


def register(conn) -> dict:
    ids = lookup(conn)
    for rid, _, statement in RULES:
        if title_of(rid) not in ids:
            ids[title_of(rid)] = add_hypothesis(conn, title_of(rid), statement + f" (see {MEMO}); pre-registered bar and windows in the memo.",
                                                rationale="Round 15: conditioning ideas from the third deep-research report of 2026-10-17.",
                                                research_memo=MEMO, strategy="round15_filters.py")
    return {rid: ids[title_of(rid)] for rid, _, _ in RULES}
