# NEXUS milestone checklist

- [x] **M1 Specification and skeleton** - package, config, typed models, schema + migrations, immutable audit log, instrument registry, three separate ledger accounts, data-lineage record, secrets handling, no-live-trading invariant, governance lock, tests, CI (existing `tests` workflow).
- [x] **M2 Data foundation** - NYSE + 24/7 calendars, bars table with lineage (migration 002), read-only adapter protocol + fixture adapter, quality checks (OHLC sanity, duplicates, calendar gaps, source conflict, freshness), idempotent ingestion, point-in-time reads, `DecisionDataGate` that blocks stale/missing/unknown data and respects the halt switch.
  - Limits: no real vendor adapter yet (no entitlements assumed; needs your vendor choice); daily bars only; NYSE ad hoc closures must be added by hand; no futures/options contract metadata yet.
- [ ] M3 Portfolio accounting and shadow state
- [ ] M4 Simulator and paper ledger
- [ ] M5 Research and backtest framework
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
