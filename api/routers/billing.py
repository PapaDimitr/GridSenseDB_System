#/billing endpoints — backed by PostgreSQL (asyncpg).

import json

import asyncpg
from fastapi import APIRouter, HTTPException

from db.postgres import get_pool
from models.postgres import AccountOut, InvoiceIn, InvoiceOut

router = APIRouter(prefix="/billing", tags=["Billing & Accounts"])


@router.get("/account/{premise_id}", response_model=AccountOut)
async def get_account(premise_id: str):
    """Account details + current balance for a premise."""
    SELECT_ACCOUNT = """
    """
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(SELECT_ACCOUNT, premise_id)

    if row is None:
        raise HTTPException(status_code=404,
                            detail=f"No billing account for premise '{premise_id}'")

    data = dict(row)
    if data.get("tariff") is not None:
        data["tariff"] = json.loads(data["tariff"])
    return AccountOut(**data)


@router.post("/invoice", response_model=InvoiceOut)
async def create_invoice(inv: InvoiceIn):
    """Generate a monthly invoice — insert the invoice AND adjust the account
    balance atomically (the ACID transaction)."""
    invoice_id = f"{inv.premise_id}:{inv.period}"

    INSERT_INVOICE = """
    """
    UPDATE_BALANCE = """
    """

    async with get_pool().acquire() as conn:
        # transaction() = ACID: the INSERT and the UPDATE both commit, or
        # neither does.
        async with conn.transaction():
            try:
                inserted = await conn.fetchrow(
                    INSERT_INVOICE, invoice_id, inv.premise_id, inv.period, inv.amount)
            except asyncpg.UniqueViolationError:
                # same invoice_id already exists
                raise HTTPException(status_code=409,
                                    detail=f"Invoice for {inv.period} already exists")
            except asyncpg.ForeignKeyViolationError:
                # premise has no billing account
                raise HTTPException(status_code=404,
                                    detail=f"No billing account for premise '{inv.premise_id}'")

            updated = await conn.fetchrow(UPDATE_BALANCE, inv.amount, inv.premise_id)

    return InvoiceOut(
        invoice_id=invoice_id,
        premise_id=inv.premise_id,
        period=inv.period,
        amount=inv.amount,
        new_balance=float(updated["balance"]),
        issued_at=inserted["issued_at"],
    )