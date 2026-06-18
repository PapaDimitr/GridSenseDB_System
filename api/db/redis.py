# Redis connection (dashboard cache + Pub/Sub fault alerts).

import os
import asyncio

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://cache:6379/0")

client: redis.Redis | None = None


async def connect(retries: int = 8, delay: int = 5) -> redis.Redis:
    """Open the client and verify with PING, retrying until Redis is ready."""
    global client
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # decode_responses=True → commands return str instead of bytes.
            client = redis.from_url(REDIS_URL, decode_responses=True)
            await client.ping()
            print(f"[Redis] connected on attempt {attempt}")
            return client
        except Exception as err:
            last_err = err
            print(f"[Redis] not ready ({attempt}/{retries}): {err}")
            await asyncio.sleep(delay)
    raise RuntimeError(f"Redis unreachable after {retries} tries: {last_err}")


def get_client() -> redis.Redis:
    if client is None:
        raise RuntimeError("Redis client not initialised")
    return client


async def close() -> None:
    if client is not None:
        await client.aclose()
        print("[Redis] connection closed")