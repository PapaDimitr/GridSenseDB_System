"""Pydantic models for the equipment catalog (MongoDB).

The contract is deliberately minimal: `asset_id` is the only required field
(it's the lookup key). Everything else is manufacturer/generation-specific and
varies per record, so `extra="allow"` keeps arbitrary fields instead of
dropping them — this is the flexibility that justifies MongoDB (A.5 / §2.3).
"""
from pydantic import BaseModel, ConfigDict


class EquipmentIn(BaseModel):
    """Body for POST /equipment — register new equipment."""
    model_config = ConfigDict(extra="allow")   # arbitrary extra fields are kept
    asset_id: str


class EquipmentOut(BaseModel):
    """Returned equipment document.

    Same flexibility as the input. The Mongo `_id` (an ObjectId, not
    JSON-serialisable) is stripped in the query (projection {"_id": 0}), so it
    never reaches this model.
    """
    model_config = ConfigDict(extra="allow")
    asset_id: str


# PATCH /equipment/{asset_id} takes a partial set of fields to $set — the
# router accepts a plain `dict` for that, so no dedicated model is needed.