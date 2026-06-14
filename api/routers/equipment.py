"""/equipment endpoints — backed by MongoDB (flexible equipment catalog).

Async routes: Motor is an async driver, so these use `async def` + `await`.
"""
from fastapi import APIRouter, HTTPException

from models.mongo import EquipmentIn, EquipmentOut
from db.mongo import get_mongo_session

router = APIRouter(prefix="/equipment", tags=["Equipment Data Catalog"])


def _collection():
    """The equipment collection handle (db comes from db/mongo.py)."""
    return get_mongo_session()["equipment"]


@router.get("/{asset_id}", response_model=EquipmentOut)
async def get_equipment_metadata(asset_id: str):
    """Full metadata for a single piece of equipment."""
    # {"_id": 0} strips Mongo's ObjectId so the response is JSON-serialisable.
    doc = await _collection().find_one({"asset_id": asset_id}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404,
                            detail=f"Equipment '{asset_id}' not found")
    return doc


@router.post("", status_code=201)
async def post_new_equipment(equipment: EquipmentIn):
    """Register new equipment — asset_id + any manufacturer-specific fields."""
    doc = equipment.model_dump()
    # insert_one mutates `doc` (adds an ObjectId _id), so we return the
    # asset_id rather than the doc itself.
    await _collection().insert_one(doc)
    return {"status": "created", "asset_id": equipment.asset_id}


@router.patch("/{asset_id}")
async def update_equipment(asset_id: str, fields: dict):
    """Update (set) fields on existing equipment."""
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    fields.pop("asset_id", None)   # the key itself is not editable
    res = await _collection().update_one({"asset_id": asset_id},
                                         {"$set": fields})
    if res.matched_count == 0:
        raise HTTPException(status_code=404,
                            detail=f"Equipment '{asset_id}' not found")
    return {"status": "updated", "asset_id": asset_id,
            "modified": res.modified_count}