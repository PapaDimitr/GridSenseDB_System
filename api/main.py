from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import cassandra as cass, neo4j as graph, mongo, postgres, redis
from routers import sensors, grid, equipment, billing, alerts, summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to Cassandra and apply the schema (init.cql).
    session = cass.connect()
    cass.apply_init_cql(session)

    #Startup: connect to Neo4j and seed the graph once (if empty)
    await graph.connect()
    await graph.seed_if_empty()

    #Startup; connect to MongoDB instance
    await mongo.connect()

    #Startup: connect to the PostgreSQL pool
    await postgres.connect()

    #Startup: connect to Redis (cache + Pub/Sub)
    await redis.connect()

    yield

    # Shutdown: close the Cassandra connection cleanly.
    cass.close()
    # Shutdown: close the Neo4j connection cleanly.
    await graph.close()
    # Shutdown: close the MongoDB connection cleanly.
    mongo.close()
    # Shutdown: close the PostgreSQL pool cleanly.
    await postgres.close()
    # Shutdown: close the Redis connection cleanly.
    await redis.close()

app = FastAPI(title="GridSense API", version="0.2.0", lifespan=lifespan)
app.include_router(sensors.router)
app.include_router(grid.router)
app.include_router(equipment.router)
app.include_router(billing.router)
app.include_router(alerts.router)
app.include_router(summary.router)


@app.get("/")
def root():
    return {"service": "GridSense API", "status": "up"}


@app.get("/health")
def health():
    """Liveness probe — confirms the API container is serving."""
    return {"status": "healthy"}