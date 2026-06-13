"""Pydantic models for sensor readings (Cassandra)."""
from datetime import datetime

from pydantic import BaseModel


class SensorReadingIn(BaseModel):
    sensor_id: str
    metric_type: str            # 'voltage' | 'current' | 'power_factor' | 'temp'
    value: float
    unit: str
    quality_flag: int = 0       # 0=good, 1=suspect, 2=bad
    reading_time: datetime | None = None   # server fills now() if omitted


class SensorReadingOut(BaseModel):
    sensor_id: str
    reading_time: datetime
    metric_type: str
    value: float
    unit: str
    quality_flag: int | None = None
