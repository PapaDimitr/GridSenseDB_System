# Pydantic models for billing (PostgreSQL).
# Maps to the `billing_accounts` and `invoices` tables in postgres/init.sql.

from datetime import datetime

from pydantic import BaseModel


class AccountOut(BaseModel):
    account_id: str
    premise_id: str
    tariff: dict | None = None      # JSONB column (decode the string in the router)
    balance: float
    created_at: datetime


class InvoiceIn(BaseModel):
    premise_id: str
    period: str                     # billing period, e.g. "2026-06"
    amount: float


class InvoiceOut(BaseModel):
    invoice_id: str          # TEXT natural key, e.g. "PREM_1:2026-06"
    premise_id: str
    period: str
    amount: float
    new_balance: float
    issued_at: datetime