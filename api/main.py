"""GridSense API — entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import cassandra as cass, neo4j as graph
from routers import sensors, grid


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to Cassandra and apply the schema (init.cql).
    session = cass.connect()
    cass.apply_init_cql(session)
    #Startup: connect to Neo4j and seed the graph once (if empty)
    graph.connect()
    graph.seed_if_empty()
    yield
    # Shutdown: close the Cassandra connection cleanly.
    cass.close()
    # Shutdown: close the Neo4j connection cleanly.
    graph.close()

app = FastAPI(title="GridSense API", version="0.2.0", lifespan=lifespan)
app.include_router(sensors.router)
app.include_router(grid.router)


@app.get("/")
def root():
    return {"service": "GridSense API", "status": "up"}


@app.get("/health")
def health():
    """Liveness probe — confirms the API container is serving."""
    return {"status": "healthy"}
