# Pydantic models for the Redis-backed endpoints.

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FaultAlertIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    node_id: str
    severity: str = "warning"        # "info" | "warning" | "critical"
    message: str


class FaultAlert(FaultAlertIn):
    timestamp: datetime


class SensorSummary(BaseModel):
    # Cached summary for GET /sensors/{sensor_id}/summary (TTL 30s).
    sensor_id: str
    latest_value: float | None = None
    latest_time: datetime | None = None
    count_1h: int = 0
    min_1h: float | None = None
    max_1h: float | None = None
    avg_1h: float | None = None
    cached: bool = False             # True when served from the Redis cache