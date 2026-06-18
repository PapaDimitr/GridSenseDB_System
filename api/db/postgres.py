# PostgreSQL connection pool (billing & accounts).
import os
import asyncio

import asyncpg

DSN = os.getenv("POSTGRES_DSN")

_pool: asyncpg.Pool | None = None


async def connect(retries: int = 8, delay: int = 5) -> asyncpg.Pool:
    """Create the pool, retrying until Postgres accepts connections."""
    global _pool
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            _pool = await asyncpg.create_pool(DSN, min_size=1, max_size=10)
            async with _pool.acquire() as conn:
                await conn.execute("SELECT 1")   # verify connectivity
            print(f"[PostgreSQL] connected on attempt {attempt}")
            return _pool
        except Exception as err:
            last_err = err
            print(f"[PostgreSQL] not ready ({attempt}/{retries}): {err}")
            await asyncio.sleep(delay)
    raise RuntimeError(f"PostgreSQL unreachable after {retries} tries: {last_err}")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("PostgreSQL pool not initialised")
    return _pool


async def close() -> None:
    if _pool is not None:
        await _pool.close()
        print("[PostgreSQL] connection closed")