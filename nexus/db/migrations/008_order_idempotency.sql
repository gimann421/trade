-- Duplicate-order prevention: a retried job that re-proposes the same decision gets the original order back.
ALTER TABLE orders ADD COLUMN client_key TEXT;
CREATE UNIQUE INDEX orders_client_key ON orders (account_id, client_key) WHERE client_key IS NOT NULL;
