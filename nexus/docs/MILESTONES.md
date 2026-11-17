# NEXUS milestone checklist

- [x] **M1 Specification and skeleton** - package, config, typed models, schema + migrations, immutable audit log, instrument registry, three separate ledger accounts, data-lineage record, secrets handling, no-live-trading invariant, governance lock, tests, CI (existing `tests` workflow).
- [x] **M2 Data foundation** - NYSE + 24/7 calendars, bars table with lineage (migration 002), read-only adapter protocol + fixture adapter, quality checks (OHLC sanity, duplicates, calendar gaps, source conflict, freshness), idempotent ingestion, point-in-time reads, `DecisionDataGate` that blocks stale/missing/unknown data and respects the halt switch.
  - Limits: no real vendor adapter yet (no entitlements assumed; needs your vendor choice); daily bars only; NYSE ad hoc closures must be added by hand; no futures/options contract metadata yet.
- [x] **M3 Portfolio accounting, real-portfolio view and shadow ledger** - exact-Decimal append-only journal, immutable owner-confirmed ACTUAL snapshots (history kept, hash-verified), shadow ledger opened from an actual snapshot (actual never touched; DB triggers block cross-ledger entries), explicit reset/merge/parallel decision log, fail-closed NAV, reconciliation, holdings CSV import (works today), Schwab read-only boundary (GET + accounts/positions allowlist, orders refused).
  - Limits: no live Schwab connection (owner must create a Schwab developer app and complete OAuth; tokens env-only); single currency; no tax lots, corporate-action automation or recommendations engine yet (recommendations arrive with the risk gate and agents).
- [x] **M4 Simulator, risk gate, paper order lifecycle** - orders/transition tables (immutable, append-only), pre-registered DECISION events (no backdating), deterministic risk gate (no leverage/shorts/derivatives, tier, max weight, cash, NAV marks; ACTUAL ledger can never be ordered against), conservative next-session-open fill model with slippage, half-spread, 1% volume cap, DAY expiry and no look-ahead, deterministic replay, and the paper-only Alpaca adapter (paper endpoint only, env keys, PAPER_SLEEVE + risk-approved orders only, client_order_id idempotency).
  - Limits: paper-broker FILLS are not yet reconciled back into the sleeve ledger (needs real keys to verify the response shapes); no futures/options/FX models; financing, borrow and tax modeling absent; slippage numbers are placeholders until measured.
- [x] **M5 Research, backtest and independent promotion** - hypothesis registry (spec 6.1 fields, pre-registered numeric success criteria, immutable versions, hash-checked), reproducible long-only daily backtest engine (decide at close, trade next open, adverse costs, no look-ahead, no leverage), experiments recorded with code commit + config hash + snapshot ids + result hash, single-use holdout (enforced in code and by a unique DB index), cost-sensitivity via `cost_multiplier`, and the Q0-Q7 promotion workflow (no skipping, author can never promote their own strategy, Red Team/committee roles, Q4 criteria recomputed from stored results and blocked on unknown/dirty commits, Q5 needs paper_plan + R2 universe, Q6 against pre-registered minimums, Q7 grants nothing).
  - Limits: engine is daily long-only (no shorts, futures, options, borrow, taxes, financing); multiple-testing correction is not automated (the number of hypotheses tried must be reported by the author and weighed by the committee); walk-forward is a manual sequence of registered segments for now; roles are labels, not authenticated identities (real separation arrives with M6/M7).
- [ ] M6 Agent layer
- [ ] M7 Continuous orchestration
- [ ] M8 Dashboard and attribution
- [ ] M9 Shadow validation period

## Assumptions
1. Lives in `nexus/` inside gimann421/trade, fully isolated from `core/`, `strategies/`, `paper/` (import ban is tested). Whether to move to its own repo is an open question for the owner.
2. SQLite for M1 (zero infra, tests run anywhere); SQL is portable and Postgres is the intended production store. Parquet/Redis/FastAPI are deferred until a milestone needs them.
3. Python stdlib + PyYAML only; no new dependencies, so existing CI is unchanged.
4. Owner inputs (base currency, drawdown limit, brokers, vendors) are left `null` and reported as unconfirmed; nothing guesses them.
5. Limits in `risk_limits.yaml` are structural launch defaults only (no leverage, no shorts, no derivatives).

## Known limitations (M1)
- Governance lock detects edits (fail closed at boot) but cannot stop someone with repo write access from re-locking; protect with CODEOWNERS/branch protection on `nexus/config/`, `nexus/docs/01_CONSTITUTION.md` and `governance.lock.json`.
- SQLite triggers block UPDATE/DELETE, but anyone with file access can drop them; the hash chain detects this on verify, and the chain head should be anchored externally (M7).
- No risk gate, order lifecycle, accounting or adapters yet; the order state machine is defined as data only.
- Audit chain verify is O(n) per call; add checkpoints once volume warrants.

## Owner authorization log
- 2026-11-05, Garret: paper trading is fine. Recorded in `config/permissions.yaml` as `paper_broker_order`, pinned to `https://paper-api.alpaca.markets` (`nexus/paper_guard.py`). Live trading, broker_write and money movement stay forbidden. The order adapter itself arrives in Milestone 4; Milestone 2 (data foundation) is next.
- 2026-11-05, Garret: NEXUS stays in the trade repo.

## Real-portfolio recommendations (read-only, advisory)
`nexus/recommendations.py`: deterministic generators (single-name and theme concentration, tax-loss candidates with wash-sale/holding-period caveats, cash share, stale snapshot) recorded as immutable, pre-registered findings tied to the exact snapshot; owner responses and outcomes are appended notes. It cannot place orders (tested). Holdings, prices and theme tags are supplied from local untracked files, never committed. Limits: thresholds are review prompts, not owner limits; tax logic is generic (taxable status unconfirmed, other accounts not modeled by owner request); LLM-written recommendations arrive in M6 through the same path.
