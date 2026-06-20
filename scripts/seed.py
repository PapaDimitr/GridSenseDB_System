# GridSense data seeder 
# Run from the project root after `docker compose up`:

import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Self-bootstrap deps so `python scripts/seed.py` runs as a single command.
import importlib.util
import subprocess
import sys
_DEPS = {"cassandra": "cassandra-driver", "neo4j": "neo4j", "pymongo": "pymongo",
         "psycopg2": "psycopg2-binary", "dotenv": "python-dotenv"}
_missing = [pkg for mod, pkg in _DEPS.items() if importlib.util.find_spec(mod) is None]
if _missing:
    print(f"[seed] installing missing deps: {', '.join(_missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *_missing])

from dotenv import load_dotenv
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args
from neo4j import GraphDatabase
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import Json

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Host-facing config: the script runs on the host, so it uses localhost + the
# exposed ports (not the compose service names).
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", os.getenv("NEO4J_PASSWORD", "gridsense_dev"))
MONGO_URI = (f"mongodb://{os.getenv('MONGO_USER','gridsense')}:"
             f"{os.getenv('MONGO_PASSWORD','gridsense_dev')}@localhost:27017")
PG = dict(host="localhost", port=5432,
          dbname=os.getenv("POSTGRES_DB", "gridsense"),
          user=os.getenv("POSTGRES_USER", "gridsense"),
          password=os.getenv("POSTGRES_PASSWORD", "gridsense_dev"))
CASSANDRA_HOSTS = ["localhost"]


def seed_neo4j():
    # 1 GSP -> 10 substations -> 40 transformers -> 200 meters
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    tx_count = sm_count = 0
    with driver.session() as s:
        s.run("MERGE (g:GridSupplyPoint {node_id:'GSP_NORTH'}) "
              "SET g.name='Northern Grid Supply Point', g.voltage_kV=132")
        for i in range(1, 11):
            ss = f"SS_{i:03d}"
            s.run("""
                MERGE (s:Substation {node_id:$id}) SET s.name=$name, s.voltage_kV=11
                WITH s MATCH (g:GridSupplyPoint {node_id:'GSP_NORTH'})
                MERGE (g)-[:FEEDS]->(s)
            """, id=ss, name=f"Substation {i}")
            for j in range(1, 5):
                tx = f"TX_{i:03d}_{j}"
                tx_count += 1
                s.run("""
                    MERGE (t:Transformer {node_id:$tid}) SET t.name=$name, t.rating_kVA=400
                    WITH t MATCH (s:Substation {node_id:$sid})
                    MERGE (s)-[:SUPPLIES]->(t)
                """, tid=tx, name=f"Transformer {tx}", sid=ss)
                for k in range(1, 6):
                    sm = f"SM_{i:03d}_{j}_{k}"
                    sm_count += 1
                    s.run("""
                        MERGE (m:SmartMeter {node_id:$mid}) SET m.name=$name, m.phase='single'
                        WITH m MATCH (t:Transformer {node_id:$tid})
                        MERGE (t)-[:CONNECTS_TO]->(m)
                    """, mid=sm, name=f"Meter {sm}", tid=tx)
    driver.close()
    print(f"[neo4j] 10 substations, {tx_count} transformers, {sm_count} meters")


def seed_cassandra(retries=10, delay=5):
    # 50,000 readings across 20 sensors.
    cluster = session = None
    for attempt in range(1, retries + 1):
        try:
            cluster = Cluster(CASSANDRA_HOSTS)
            session = cluster.connect("gridsense")
            break
        except Exception as err:
            print(f"[cassandra] not ready ({attempt}/{retries}): {err}")
            time.sleep(delay)
    if session is None:
        raise RuntimeError("Cassandra unreachable (is the stack up and the API initialised?)")

    insert = session.prepare(
        "INSERT INTO sensor_readings "
        "(sensor_id, reading_time, metric_type, value, unit, quality_flag) "
        "VALUES (?, ?, ?, ?, ?, ?)")
    random.seed(42)
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)   # fixed base => idempotent
    metrics = [("voltage", "V", 230.0, 10.0), ("current", "A", 15.0, 5.0),
               ("power_factor", "", 0.95, 0.05), ("temp", "C", 40.0, 8.0)]
    rows = []
    for i in range(20):
        sensor_id = f"S_{i:03d}"
        metric, unit, mean, spread = metrics[i % len(metrics)]
        for k in range(2500):
            rows.append((sensor_id, base + timedelta(seconds=k), metric,
                         round(random.gauss(mean, spread), 3), unit, 0))
    execute_concurrent_with_args(session, insert, rows, concurrency=64)
    cluster.shutdown()
    print(f"[cassandra] {len(rows)} readings across 20 sensors")


def seed_mongo():
    # 30 equipment records, 3 types, each a different field shape
    client = MongoClient(MONGO_URI)
    coll = client["CatalogDB"]["equipment"]
    docs = []
    for n in range(1, 11):
        docs.append({"asset_id": f"TX_{n:03d}", "type": "transformer",
                     "manufacturer": "ABB", "rating_kVA": 400, "cooling": "ONAN"})
    for n in range(1, 11):
        docs.append({"asset_id": f"SW_{n:03d}", "type": "switchgear",
                     "voltage_kV": 11, "ip_rating": "IP54"})
    for n in range(1, 11):
        docs.append({"asset_id": f"MT_{n:03d}", "type": "smart_meter",
                     "tariff_class": "residential", "phase": "single"})
    for d in docs:
        coll.replace_one({"asset_id": d["asset_id"]}, d, upsert=True)
    client.close()
    print(f"[mongo] {len(docs)} equipment records (3 types)")


def seed_postgres():
    # 100 accounts + 2 invoices each
    conn = psycopg2.connect(**PG)
    conn.autocommit = True
    cur = conn.cursor()
    random.seed(7)
    accounts = invoices = 0
    for n in range(1, 101):
        acc, prem = f"ACC_{n:03d}", f"PREM_{n:03d}"
        tariff = Json({"plan": "residential" if n % 2 else "commercial",
                       "rate": round(random.uniform(0.10, 0.30), 2)})
        cur.execute(
            "INSERT INTO billing_accounts (account_id, premise_id, tariff, balance) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (premise_id) DO NOTHING",
            (acc, prem, tariff, 0))
        accounts += 1
        for period in ("2026-04", "2026-05"):
            cur.execute(
                "INSERT INTO invoices (invoice_id, premise_id, period, amount) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (invoice_id) DO NOTHING",
                (f"{prem}:{period}", prem, period, round(random.uniform(20, 120), 2)))
            invoices += 1
    cur.close()
    conn.close()
    print(f"[postgres] {accounts} accounts, {invoices} invoices")


def main():
    for fn in (seed_neo4j, seed_cassandra, seed_mongo, seed_postgres):
        try:
            fn()
        except Exception as err:
            print(f"[seed] {fn.__name__} FAILED: {err}")
    print("[seed] done")


if __name__ == "__main__":
    main()
