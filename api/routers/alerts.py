#/alerts endpoints — backed by Redis (Pub/Sub + a capped 'active' list).
import json
from datetime import datetime, timezone

from fastapi import APIRouter

from db.redis import get_client
from models.redis import FaultAlertIn, FaultAlert

router = APIRouter(prefix="/alerts", tags=["Fault Alerts"])

ALERTS_CHANNEL = "fault-alerts"     # Pub/Sub channel subscribers listen on
ALERTS_KEY = "alerts:active"        # capped list backing GET /alerts/active
MAX_ALERTS = 100


@router.post("/publish", status_code=201)
async def publish_alert(alert: FaultAlertIn):
    """Store the alert on the active list AND publish it to subscribers."""
    redis = get_client()

    data = alert.model_dump()
    data.pop("timestamp", None)
    full = FaultAlert(**data, timestamp=datetime.now(timezone.utc))
    payload = full.model_dump_json()

    await redis.lpush(ALERTS_KEY, payload)          # newest first
    await redis.ltrim(ALERTS_KEY, 0, MAX_ALERTS - 1)  # cap the list
    subscribers = await redis.publish(ALERTS_CHANNEL, payload)
    return {"status": "published", "subscribers": subscribers}


@router.get("/active", response_model=list[FaultAlert])
async def active_alerts(limit: int = 50):
    """The most recent active fault alerts (newest first)."""
    redis = get_client()
    items = await redis.lrange(ALERTS_KEY, 0, limit - 1)
    return [FaultAlert(**json.loads(item)) for item in items]