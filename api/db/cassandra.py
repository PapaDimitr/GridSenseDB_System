"""Cassandra connection and schema bootstrap.

The official Cassandra image does NOT auto-run init.cql, so the API applies it
on startup. This keeps `docker compose up --build` a single step (no manual
schema-load), which the B.1 rules require.
"""
import os
import time

from cassandra.cluster import Cluster, Session

CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "timeseries-db").split(",")
KEYSPACE = "gridsense"
INIT_CQL_PATH = os.getenv("INIT_CQL_PATH", "/app/cql/init.cql")

_cluster: Cluster | None = None
_session: Session | None = None


def connect(retries: int = 12, delay: int = 5) -> Session:
    """Open a session, retrying until Cassandra accepts CQL connections.

    `depends_on: service_healthy` waits for the node to be UP, but the native
    CQL port can need a few more seconds — hence the retry loop.
    """
    global _cluster, _session
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            _cluster = Cluster(CASSANDRA_HOSTS)
            _session = _cluster.connect()
            print(f"[cassandra] connected on attempt {attempt}")
            return _session
        except Exception as err:  # NoHostAvailable, etc.
            last_err = err
            print(f"[cassandra] not ready ({attempt}/{retries}): {err}")
            time.sleep(delay)
    raise RuntimeError(f"Cassandra unreachable after {retries} tries: {last_err}")


def _statements(script: str) -> list[str]:
    """Strip `--` comments (including ones that contain ';'), then split on ';'.

    Stripping comments first matters: init.cql has a comment containing a
    semicolon, which would otherwise split a statement in the wrong place.
    """
    no_comments = []
    for line in script.splitlines():
        i = line.find("--")
        no_comments.append(line if i == -1 else line[:i])
    body = "\n".join(no_comments)
    return [s.strip() for s in body.split(";") if s.strip()]


def apply_init_cql(session: Session, path: str = INIT_CQL_PATH) -> None:
    """Execute every statement in init.cql (driver runs one at a time)."""
    with open(path, "r", encoding="utf-8") as fh:
        stmts = _statements(fh.read())
    for stmt in stmts:
        session.execute(stmt)
    session.set_keyspace(KEYSPACE)
    print(f"[cassandra] applied {len(stmts)} schema statements")


def get_session() -> Session:
    if _session is None:
        raise RuntimeError("Cassandra session not initialised")
    return _session


def close() -> None:
    if _cluster is not None:
        _cluster.shutdown()
        print("[cassandra] connection closed")
