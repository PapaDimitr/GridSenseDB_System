"""MongoDB connection (equipment catalog).

Motor is async, so connect() is awaited from the lifespan. We keep two
module-level refs: the client (needed to close the connection pool) and the
database handle (what the routers actually use).
"""
import os
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient

URI = os.getenv("MONGO_URI")
DB_NAME = "CatalogDB"

_client: AsyncIOMotorClient | None = None
mongo_session = None  # database handle: _client[DB_NAME]


async def connect(retries: int = 8, delay: int = 5):
    """Open the client and verify connectivity (ping), retrying until ready."""
    global _client, mongo_session
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            _client = AsyncIOMotorClient(URI)
            await _client.admin.command("ping")   # actually verifies the connection
            mongo_session = _client[DB_NAME]
            print(f"[MongoDB] connected on attempt {attempt}")
            return mongo_session
        except Exception as err:
            last_err = err
            print(f"[MongoDB] not ready ({attempt}/{retries}): {err}")
            await asyncio.sleep(delay)
    raise RuntimeError(f"MongoDB unreachable after {retries} tries: {last_err}")


def get_mongo_session():
    if mongo_session is None:
        raise RuntimeError("MongoDB session not initialised")
    return mongo_session


def close() -> None:
    # Close the CLIENT (the database handle has no close()).
    if _client is not None:
        _client.close()
        print("[MongoDB] connection closed")
