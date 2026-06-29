# GridSense — Smart-Grid Analytics Platform

A FastAPI gateway over five storage technologies, each chosen for a specific access pattern in the smart-grid scenario. The whole stack starts and seeds itself with a single command.

| Store role | Technology | Container | Port | Why |
|---|---|---|---|---|
| Sensor time-series | Apache Cassandra 4.1 | `gridsense_cassandra` | 9042 | Write-heavy, partition by sensor + time |
| Network topology | Neo4j 5 Community | `gridsense_neo4j` | 7474 / 7687 | First-class relationships, Cypher traversal for fault paths |
| Equipment metadata | MongoDB 7 | `gridsense_mongo` | 27017 | Flexible per-model schema |
| Billing & accounts | PostgreSQL 15 | `gridsense_postgres` | 5432 | ACID transactions, JSONB tariffs |
| Dashboard cache & alerts | Redis 7 | `gridsense_redis` | 6379 | Sub-ms reads; TTL expiry, Pub/Sub |
| REST gateway | FastAPI (Python 3.11) | `gridsense_api` | 8000 | All business logic |

## Prerequisites

- Docker and Docker Compose v2 (`docker compose`, not the legacy `docker-compose`).

## Setup

Credentials are **never hard-coded** in `docker-compose.yml`; they are injected from a `.env` file. A `.env` with **non-sensitive dev defaults** is committed so the stack runs from one command, as the assignment requires, no manual setup step is needed. To use your own credentials, edit the values in `.env`.

## Run

```bash
docker compose up --build
```

That single command:
1. builds the API image (all drivers baked in via `requirements.txt`),
2. starts the five databases and waits for each to pass its health check,
3. starts the API, which applies the Cassandra schema (`cql/init.cql`) on startup,
4. runs the one-shot **`seed`** service, which loads demo data and then exits.

No manual intermediate steps are required. When `gridsense_seed` logs `[seed] done` and exits 0, the system is ready at `http://localhost:8000`.

Seed data: 10 substations / 40 transformers / 200 meters (Neo4j), 50,000 readings across 20 sensors (Cassandra), 30 equipment records (MongoDB), 100 accounts + 200 invoices (PostgreSQL). The seeder is **idempotent** and re-running it creates no duplicates.

## Example requests

```bash
# 1. Liveness
curl localhost:8000/health

# 2. Time-series read (Cassandra)
curl localhost:8000/sensors/S_000/readings

# 3. Cached summary (Redis, 30s TTL) — note the "cached" flag flips on the 2nd call
curl localhost:8000/sensors/S_000/summary

# 4. Graph traversal (Neo4j) for everything downstream of a substation, up to depth 4
curl "localhost:8000/grid/fault-impact/SS_001?max_depth=4"

# 5. Equipment metadata (MongoDB)
curl localhost:8000/equipment/TX_001

# 6. Billing account (PostgreSQL)
curl localhost:8000/billing/account/PREM_001
```

## API reference

| Method | Path | Store |
|---|---|---|
| GET | `/health` | — |
| GET | `/metrics` | observability (see below) |
| POST | `/sensors/readings` | Cassandra |
| GET | `/sensors/{sensor_id}/readings` | Cassandra |
| GET | `/sensors/{sensor_id}/summary` | Cassandra + Redis cache |
| GET | `/grid/fault-impact/{node_id}` | Neo4j |
| GET | `/grid/restore-paths/{node_id}` | Neo4j |
| POST | `/grid/nodes` | Neo4j |
| POST | `/grid/relationships` | Neo4j |
| GET | `/equipment/{asset_id}` | MongoDB |
| POST | `/equipment` | MongoDB |
| GET | `/billing/account/{premise_id}` | PostgreSQL |
| POST | `/billing/invoice` | PostgreSQL |
| POST | `/alerts/publish` | Redis Pub/Sub |
| GET | `/alerts/active` | Redis |

Interactive docs: `http://localhost:8000/docs`.

## Observability

Every endpoint is instrumented via `prometheus-fastapi-instrumentator`. Per-endpoint **request count**, **error rate** (status-code labels), and a **latency histogram** (for percentiles) are exposed at `GET /metrics`:

```bash
# generate traffic
curl -s localhost:8000/sensors/S_000/readings > /dev/null

curl -s localhost:8000/metrics | grep 'http_requests_total{'
```

Percentiles are derived from `http_request_duration_seconds` via `histogram_quantile`.

## Benchmarks (Part C)

Measurement scripts live in `scripts/bench/` (Cassandra throughput vs consistency level, graph traversal latency vs depth, Redis cache effectiveness, MongoDB vs PostgreSQL JSONB). Run them from the project root after the stack is up, e.g.:

```bash
python scripts/bench/c3_redis_cache.py
```

> **Note:** `c1_cassandra_throughput.py` (9 interleaved rounds of concurrent writes) and `c3b_eviction_policy.py` (10,000 cache requests across two eviction policies) are intentionally heavy and can take a while to finish, let them run to completion.

## Repository layout

```
api/            FastAPI app
cql/            Cassandra schema (init.cql)
postgres/       PostgreSQL schema (init.sql)
neo4j/          Neo4j seed assets
scripts/        seed.py + bench/ measurement scripts
docker-compose.yml
```