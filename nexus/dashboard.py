"""Static HTML dashboard rendered from the database (spec 14). Read-only; actual, shadow and paper views are separate.

Everything dynamic is HTML-escaped. The output contains the owner's real holdings, so it is written only to local,
untracked locations (never committed or published). A position with no fresh priced bar is shown as unpriceable;
a clearly-labelled fallback mark may be supplied by the caller (e.g. a screenshot price) and is flagged as such.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from decimal import Decimal

from .accounting import ZERO, actual_state, load_snapshot, state_from_entries, verify_cash_identity
from .domain.enums import LedgerKind
from .errors import NexusError
from .health import report as health_report
from .ingestion import DecisionDataGate, bars_known_at
from .scheduler import JobSpec
from .store import Store
from .timeutil import to_iso

e = lambda x: html.escape(str(x), quote=True)


def _marks(store: Store, iids, now, fallback: dict[str, Decimal] | None):
    marks, notes = {}, {}
    gate = DecisionDataGate(store)
    for i in iids:
        bars = bars_known_at(store, i, now)
        fresh = bool(bars) and gate.check(i, now).ok
        if bars and fresh:
            marks[i] = Decimal(str(bars[-1].close)); notes[i] = f"bar {bars[-1].session_date}"
        elif fallback and i in fallback:
            marks[i] = fallback[i]; notes[i] = "FALLBACK mark (not a fresh feed bar)"
        elif bars:
            marks[i] = Decimal(str(bars[-1].close)); notes[i] = f"STALE bar {bars[-1].session_date}"
        else:
            notes[i] = "UNPRICEABLE"
    return marks, notes


def _ledger_view(store: Store, account_id: str, state, now, fallback):
    marks, notes = _marks(store, state.positions, now, fallback)
    unpriced = [i for i in state.positions if i not in marks]
    value = sum((q * marks[i] for i, q in state.positions.items() if i in marks), ZERO)
    flagged = [i for i, n in notes.items() if not n.startswith("bar ")]
    rows = "".join(
        f"<tr><td>{e(i.rsplit(':', 1)[-1])}</td><td class=n>{e(q)}</td><td class=n>{e(marks[i].quantize(Decimal('0.01'))) if i in marks else '-'}</td>"
        f"<td class=n>{e((q * marks[i]).quantize(Decimal('1'))) if i in marks else '-'}</td><td>{e(notes[i])}</td></tr>"
        for i, q in sorted(state.positions.items(), key=lambda t: -(t[1] * marks.get(t[0], ZERO))))
    nav = state.cash + value
    warn = (f"<p class=warn>NAV is incomplete: unpriceable {', '.join(e(i.rsplit(':', 1)[-1]) for i in unpriced)}.</p>" if unpriced else "")
    warn += (f"<p class=warn>{len(flagged)} position(s) use a non-fresh or fallback mark.</p>" if flagged else "")
    return nav, f"<table><tr><th>Symbol</th><th>Qty</th><th>Mark</th><th>Value</th><th>Mark source</th></tr>{rows}</table>{warn}"


def render(store: Store, jobs: list[JobSpec], now: datetime, fallback_marks: dict[str, Decimal] | None = None) -> str:
    sections, cards = [], []
    # --- ledgers, each separate ---
    for kind in LedgerKind:
        for a in store.list_accounts(kind):
            try:
                st = actual_state(store, a.account_id) if kind is LedgerKind.ACTUAL else state_from_entries(store, a.account_id, now)
            except NexusError as exc:
                sections.append(f"<section><h2>{e(kind.value)}: {e(a.name)}</h2><p class=warn>{e(exc)}</p></section>")
                continue
            nav, table = _ledger_view(store, a.account_id, st, now, fallback_marks)
            recon = "n/a (snapshot)"
            if kind is not LedgerKind.ACTUAL:
                try:
                    verify_cash_identity(store, a.account_id); recon = "cash identity OK"
                except NexusError as exc:
                    recon = f"FAILED: {exc}"
            cards.append(f"<div class=card><div class=k>{e(kind.value)}: {e(a.name)}</div><div class=v>${e(nav.quantize(Decimal('1')))}</div>"
                         f"<div class=s>cash ${e(st.cash.quantize(Decimal('1')))} · {len(st.positions)} positions</div></div>")
            sections.append(f"<section><h2>{e(kind.value)}: {e(a.name)}</h2><p>Reconciliation: {e(recon)}</p>{table}</section>")
    # --- recommendations ---
    recs = store.conn.execute("SELECT * FROM recommendations ORDER BY created_at DESC, rowid DESC LIMIT 40").fetchall()
    corrected = {r["rec_id"] for r in store.conn.execute("SELECT rec_id FROM recommendation_notes WHERE kind='correction'")}
    rr = "".join(f"<tr><td>{e(r['severity'])}</td><td>{e(r['kind'])}</td><td>{e(r['subject'].rsplit(':', 1)[-1])}</td>"
                 f"<td>{e(r['summary'])}{' <b>(corrected: false alarm)</b>' if r['rec_id'] in corrected else ''}</td></tr>" for r in recs)
    sections.append(f"<section><h2>Recommendations (advice only; NEXUS never trades your real account)</h2><table><tr><th>Severity</th><th>Kind</th><th>Subject</th><th>Summary</th></tr>{rr}</table></section>")
    # --- paper trading ---
    orders = store.conn.execute("SELECT o.*, (SELECT to_state FROM order_transitions t WHERE t.order_id=o.order_id ORDER BY seq DESC LIMIT 1) AS state FROM orders o ORDER BY decision_ts DESC LIMIT 40").fetchall()
    orr = "".join(f"<tr><td>{e(o['decision_ts'])}</td><td>{e(o['strategy_id'])}</td><td>{e(o['side'])} {e(o['quantity'])} {e(o['instrument_id'].rsplit(':', 1)[-1])}</td><td>{e(o['state'])}</td><td>{e(o['mode'])}</td></tr>" for o in orders)
    sections.append(f"<section><h2>Paper trading</h2><table><tr><th>Decided</th><th>Strategy</th><th>Order</th><th>State</th><th>Mode</th></tr>{orr or '<tr><td colspan=5>No orders yet</td></tr>'}</table></section>")
    # --- research ---
    hy = store.conn.execute("SELECT hyp_id, MAX(version) v FROM hypotheses GROUP BY hyp_id").fetchall()
    from .promotion import current_tier
    hr = "".join(f"<tr><td>{e(h['hyp_id'])}</td><td>v{e(h['v'])}</td><td>{e(current_tier(store, h['hyp_id'], h['v']))}</td></tr>" for h in hy)
    sections.append(f"<section><h2>Research lab</h2><table><tr><th>Hypothesis</th><th>Version</th><th>Tier</th></tr>{hr or '<tr><td colspan=3>No hypotheses registered yet</td></tr>'}</table></section>")
    # --- risk, health, audit ---
    h = health_report(store, jobs, now)
    dq = store.conn.execute("SELECT payload_json, recorded_at FROM events WHERE event_type='data.quality_failed' ORDER BY seq DESC LIMIT 8").fetchall()
    dqr = "".join(f"<li>{e(r['recorded_at'][:16])}: {e(json.loads(r['payload_json']).get('instrument_id') or json.loads(r['payload_json']).get('snapshot_id'))} - {e(json.loads(r['payload_json']).get('quality'))}</li>" for r in dq)
    probs = "".join(f"<li class=warn>{e(p)}</li>" for p in h["problems"]) or "<li>none</li>"
    sections.append(f"<section><h2>Risk, health and audit</h2><p>Emergency stop: <b>{'ACTIVE' if h['halted'] else 'off'}</b> · audit events verified: {e(h['audit_events'])} · stage 0 (no live trading, no broker write except the paper-only adapter)</p>"
                    f"<h3>Problems</h3><ul>{probs}</ul><h3>Recent data-quality failures</h3><ul>{dqr or '<li>none</li>'}</ul></section>")
    css = ("body{font:14px system-ui;margin:16px;background:#0f1115;color:#e6e6e6}h1{font-size:20px}h2{font-size:16px;margin-top:28px}"
           "table{border-collapse:collapse;width:100%;max-width:960px}td,th{border-bottom:1px solid #2a2f3a;padding:4px 8px;text-align:left}td.n{text-align:right;font-variant-numeric:tabular-nums}"
           ".cards{display:flex;gap:12px;flex-wrap:wrap}.card{background:#1a1e27;padding:12px 16px;border-radius:8px;min-width:200px}.k{color:#9aa4b2;font-size:12px}.v{font-size:22px}.s{color:#9aa4b2;font-size:12px}.warn{color:#ffb454}")
    return (f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>NEXUS dashboard</title><style>{css}</style></head><body>"
            f"<h1>NEXUS AIS dashboard</h1><p class=s>As of {e(to_iso(now))}. Private: contains your real holdings.</p><div class=cards>{''.join(cards)}</div>{''.join(sections)}</body></html>")
