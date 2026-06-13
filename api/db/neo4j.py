"""Neo4j connection + one-time graph seeding (network topology).

A single long-lived (synchronous) Driver is created at startup and reused for
every request; the driver is thread-safe and manages its own connection pool.
"""
import os
import time

from neo4j import GraphDatabase, Driver

URI = os.getenv("NEO4J_URI", "bolt://graph-db:7687")
AUTH = ("neo4j", os.getenv("NEO4J_PASSWORD"))
SEED_PATH = os.getenv("SEED_PATH", "/app/neo4j/seed.cypher")

driver: Driver | None = None


def connect(retries: int = 8, delay: int = 5) -> Driver:
    """Open the driver, retrying until Neo4j accepts connections."""
    global driver
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            driver = GraphDatabase.driver(URI, auth=AUTH)
            driver.verify_connectivity()
            print(f"[neo4j] connected on attempt {attempt}")
            return driver
        except Exception as err:
            last_err = err
            print(f"[neo4j] not ready ({attempt}/{retries}): {err}")
            time.sleep(delay)
    raise RuntimeError(f"Neo4j unreachable after {retries} tries: {last_err}")


def _cypher_statements(script: str) -> list[str]:
    """Strip `//` comments (Cypher style), then split into statements on ';'."""
    stripped = []
    for line in script.splitlines():
        i = line.find("//")
        stripped.append(line if i == -1 else line[:i])
    body = "\n".join(stripped)
    return [s.strip() for s in body.split(";") if s.strip()]


def seed_if_empty(seed_path: str = SEED_PATH) -> None:
    """Load seed.cypher ONCE — only if the graph currently has no nodes.

    seed.cypher uses CREATE, which would duplicate the entire graph on every
    restart, so we guard on the node count and skip if it's already populated.
    """
    with get_driver().session() as session:
        count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        if count > 0:
            print(f"[neo4j] graph already seeded ({count} nodes) — skipping")
            return
        with open(seed_path, "r", encoding="utf-8") as fh:
            statements = _cypher_statements(fh.read())
        for stmt in statements:
            session.run(stmt)  # each runs in its own auto-commit transaction
        print(f"[neo4j] applied {len(statements)} seed statements")


def get_driver() -> Driver:
    if driver is None:
        raise RuntimeError("Neo4j driver not initialised")
    return driver


def close() -> None:
    if driver is not None:
        driver.close()
        print("[neo4j] connection closed")