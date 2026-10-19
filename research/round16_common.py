"""Ledger entries and fixed lists for round 16 (research/r16-outside-the-box-2026-10-17.md)."""

from core.ledger import add_hypothesis
from research.round6_scan import lookup

MEMO = "research/r16-outside-the-box-2026-10-17.md"
HYPOTHESES_BEFORE = 141

# id, strategy file, one-line statement
RULES = [
    ("filing_stable_q_m", "round16_filings.py", "Holding the 20% of covered S&P 500 members whose latest 10-K/10-Q text changed least from the year-earlier filing beats the equal-weight covered members by >= 2.0%/yr net, monthly"),
    ("rev5s_h3_band40_etf", "round16_etf.py", "The 3-session band reversal rule on volatility-scaled 5-day returns, applied to liquid ETFs from a fixed list of 169 at 2 bps, beats the equal-weight eligible ETFs by >= 2.0%/yr net"),
    ("peerlag_h3_band40_s", "round16_peers.py", "Ranking S&P 500 names by the past-5-day return of their five most correlated peers minus their own improves the 3-session band reversal rule"),
]

# Fixed before any result was computed. Leveraged, inverse and volatility products are left out on purpose.
ETFS = """
XLB XLE XLF XLI XLK XLP XLU XLV XLY XLRE XLC
SPY QQQ DIA IWM IWB IWD IWF IWN IWO IWP IWS IJH IJR IJK IJJ IJS MDY VTI VTV VUG VB VO VBR VBK VOE VOT RSP MTUM QUAL USMV VLUE SPLV SPHB DVY VIG SCHD SDY NOBL
XBI IBB SMH SOXX XHB ITB XRT KRE KBE KIE XOP OIH XME XSD IYT IYR VNQ ITA XAR IHI IHF IGV HACK SKYY TAN ICLN JETS PBW FDN IYZ XTL KCE XPH PJP IEZ XES AMLP GDX GDXJ SIL
EFA EEM VWO IEFA IEMG EWJ EWG EWU EWC EWA EWZ EWY EWT EWH EWS EWW EWP EWI EWQ EWL EWD EWN EWM EZA EPOL ECH EPU THD TUR EIS INDA EPI FXI MCHI ASHR VGK VPL EZU HEDJ DXJ VNQI REM
TLT IEF SHY IEI TLH LQD HYG JNK AGG BND TIP MUB EMB BNDX VCSH VCIT VCLT BKLN MBB GOVT SPSB
GLD SLV IAU USO UNG DBC DBA DBB UUP FXE FXY FXA FXB FXC PPLT PALL CPER
""".split()


def title_of(rule_id: str) -> str:
    return f"Round 16: {rule_id}"


def register(conn) -> dict:
    ids = lookup(conn)
    for rid, strategy, statement in RULES:
        if title_of(rid) not in ids:
            ids[title_of(rid)] = add_hypothesis(conn, title_of(rid), statement + f" (see {MEMO}); pre-registered bar and windows in the memo.",
                                                rationale="Round 16: outside-the-box ideas from the fourth deep-research report of 2026-10-17.",
                                                research_memo=MEMO, strategy=strategy)
    return {rid: ids[title_of(rid)] for rid, _, _ in RULES}
