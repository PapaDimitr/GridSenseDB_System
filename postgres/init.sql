-- postgres/init.sql — billing schema

CREATE TABLE IF NOT EXISTS billing_accounts (
    account_id  TEXT PRIMARY KEY,
    premise_id  TEXT NOT NULL UNIQUE,
    tariff      JSONB,                       -- tariff rules as JSONB (A.5 / §2.3)
    balance     NUMERIC(12,2) DEFAULT 0.00,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoices(
    invoice_id TEXT PRIMARY KEY,                 -- natural key e.g. "PREM_1:2026-06" (idempotent)
    premise_id TEXT NOT NULL REFERENCES billing_accounts(premise_id),
    period     TEXT NOT NULL,
    amount     NUMERIC(12,2) NOT NULL,
    issued_at  TIMESTAMPTZ DEFAULT now()
);

-- GIN index for querying inside the JSONB tariff (per §2.3 justification)
CREATE INDEX IF NOT EXISTS idx_billing_tariff ON billing_accounts USING GIN (tariff);
