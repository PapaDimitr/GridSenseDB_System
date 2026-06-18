# GET /sensors/{sensor_id}/summary

import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from db.cassandra import get_session
from db.redis import get_client
from models.redis import SensorSummary

router = APIRouter(prefix="/sensors", tags=["Sensor Summary (cached)"])

CACHE_TTL = 30   # seconds


def _compute_summary(sensor_id: str) -> dict:
    ## Blocking: read the last hour from Cassandra and compute stats.
    session = get_session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    rows = session.execute(
        "SELECT value, reading_time FROM sensor_readings "
        "WHERE sensor_id=%s AND reading_time > %s",
        (sensor_id, cutoff),
    )
    values, latest_value, latest_time = [], None, None
    for r in rows:
        values.append(r.value)
        if latest_time is None or r.reading_time > latest_time:
            latest_time, latest_value = r.reading_time, r.value

    count = len(values)
    return {
        "sensor_id": sensor_id,
        "latest_value": latest_value,
        "latest_time": latest_time.isoformat() if latest_time else None,
        "count_1h": count,
        "min_1h": min(values) if values else None,
        "max_1h": max(values) if values else None,
        "avg_1h": (sum(values) / count) if count else None,
    }


@router.get("/{sensor_id}/summary", response_model=SensorSummary)
async def get_summary(sensor_id: str):
    redis = get_client()
    cache_key = f"sensor:summary:{sensor_id}"

    cached = await redis.get(cache_key)
    if cached is not None:
        data = json.loads(cached)
        data["cached"] = True
        return SensorSummary(**data)

    # if cache miss then compute from Cassandra off the event loop then cache 30s
    summary = await asyncio.to_thread(_compute_summary, sensor_id)
    await redis.set(cache_key, json.dumps(summary), ex=CACHE_TTL)
    summary["cached"] = False
    return SensorSummary(**summary)