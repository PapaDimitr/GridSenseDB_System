-- postgres/init.sql — billing schema (starter; extend for the billing endpoints)
-- Runs automatically on first start of the postgres container.

CREATE TABLE IF NOT EXISTS billing_accounts (
    account_id  TEXT PRIMARY KEY,
    premise_id  TEXT NOT NULL,
    tariff      JSONB,                       -- tariff rules as JSONB (A.5 / §2.3)
    balance     NUMERIC(12,2) DEFAULT 0.00,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- GIN index for querying inside the JSONB tariff (per §2.3 justification)
CREATE INDEX IF NOT EXISTS idx_billing_tariff ON billing_accounts USING GIN (tariff);
