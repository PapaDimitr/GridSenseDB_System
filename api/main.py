"""GridSense API — entry point.

B.1/B.2 milestone: a minimal app that boots so the whole stack can come up.
Routers and DB connections are added in B.5.
"""
from fastapi import FastAPI

app = FastAPI(title="GridSense API", version="0.1.0")


@app.get("/")
def root():
    return {"service": "GridSense API", "status": "up"}


@app.get("/health")
def health():
    """Liveness probe — confirms the API container is serving."""
    return {"status": "healthy"}
