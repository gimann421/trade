-- Paper/simulated order lifecycle. Orders are immutable; state changes are appended transitions.
CREATE TABLE orders (
    order_id         TEXT PRIMARY KEY,
    account_id       TEXT NOT NULL REFERENCES ledger_accounts(account_id),
    instrument_id    TEXT NOT NULL,
    side             TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity         TEXT NOT NULL,
    order_type       TEXT NOT NULL CHECK (order_type IN ('MARKET','LIMIT')),
    limit_price      TEXT,
    time_in_force    TEXT NOT NULL CHECK (time_in_force IN ('DAY')),
    strategy_id      TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    decision_ts      TEXT NOT NULL,          -- when the decision was made (pre-registered in the audit log)
    decision_event_id TEXT NOT NULL,
    data_snapshot_ids TEXT NOT NULL,
    rationale        TEXT NOT NULL,
    fill_model       TEXT NOT NULL,
    risk_json        TEXT NOT NULL,
    mode             TEXT NOT NULL CHECK (mode IN ('simulated','paper_broker'))
);
CREATE TRIGGER orders_no_update BEFORE UPDATE ON orders BEGIN SELECT RAISE(ABORT, 'orders are immutable'); END;
CREATE TRIGGER orders_no_delete BEFORE DELETE ON orders BEGIN SELECT RAISE(ABORT, 'orders are immutable'); END;

CREATE TABLE order_transitions (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT NOT NULL REFERENCES orders(order_id),
    from_state  TEXT,
    to_state    TEXT NOT NULL,
    at          TEXT NOT NULL,
    detail_json TEXT NOT NULL
);
CREATE INDEX order_transitions_order ON order_transitions (order_id, seq);
CREATE TRIGGER order_transitions_no_update BEFORE UPDATE ON order_transitions BEGIN SELECT RAISE(ABORT, 'order transitions are append-only'); END;
CREATE TRIGGER order_transitions_no_delete BEFORE DELETE ON order_transitions BEGIN SELECT RAISE(ABORT, 'order transitions are append-only'); END;
