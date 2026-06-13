"""GridSense API — entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import cassandra as cass
from routers import sensors


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to Cassandra and apply the schema (init.cql).
    session = cass.connect()
    cass.apply_init_cql(session)
    yield
    # Shutdown: close the Cassandra connection cleanly.
    cass.close()


app = FastAPI(title="GridSense API", version="0.2.0", lifespan=lifespan)
app.include_router(sensors.router)


@app.get("/")
def root():
    return {"service": "GridSense API", "status": "up"}


@app.get("/health")
def health():
    """Liveness probe — confirms the API container is serving."""
    return {"status": "healthy"}
