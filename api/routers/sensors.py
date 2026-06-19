#/sensors endpoints — backed by Cassandra (access pattern 1).

from datetime import datetime, timezone

from fastapi import APIRouter

from db.cassandra import get_session
from models.cassandra import SensorReadingIn, SensorReadingOut

router = APIRouter(prefix="/sensors", tags=["Sensors"])


@router.post("/readings", status_code=201)
def write_reading(reading: SensorReadingIn):
    """Write a single sensor reading."""
    session = get_session()
    reading_time = reading.reading_time or datetime.now(timezone.utc)
    session.execute(
        """
        INSERT INTO sensor_readings
            (sensor_id, reading_time, metric_type, value, unit, quality_flag)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (reading.sensor_id, reading_time, reading.metric_type,
         reading.value, reading.unit, reading.quality_flag),
    )
    return {"status": "written",
            "sensor_id": reading.sensor_id,
            "reading_time": reading_time}


@router.get("/{sensor_id}/readings", response_model=list[SensorReadingOut])
def last_n_readings(sensor_id: str, limit: int = 10, from_time: datetime | None = None):
    """Access pattern (1): the most recent `limit` readings for one sensor.

    Cheap because the table is partitioned by sensor_id and clustered by
    reading_time DESC — this is a single-partition read of the top `limit` rows.
    """
    session = get_session()
    # optional from_time → only readings at/after that timestamp
    where = "WHERE sensor_id = %s"
    params = [sensor_id]
    if from_time is not None:
        where += " AND reading_time >= %s"
        params.append(from_time)
    params.append(limit)
    rows = session.execute(
        f"SELECT sensor_id, reading_time, metric_type, value, unit, quality_flag "
        f"FROM sensor_readings {where} LIMIT %s",
        tuple(params),
    )
    return [
        SensorReadingOut(
            sensor_id=r.sensor_id,
            reading_time=r.reading_time,
            metric_type=r.metric_type,
            value=r.value,
            unit=r.unit,
            quality_flag=r.quality_flag,
        )
        for r in rows
    ]
