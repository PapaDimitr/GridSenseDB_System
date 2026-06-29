# schema flexibility: MongoDB vs PostgreSQL JSONB query times.
# Same 30 records in both stores 3 queries x 10 runs each; reports mean ms.
import importlib.util
import subprocess
import sys
for _mod, _pkg in (("pymongo", "pymongo"), ("psycopg2", "psycopg2-binary"),
                   ("dotenv", "python-dotenv")):
    if importlib.util.find_spec(_mod) is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", _pkg])

import os
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import Json

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MONGO_URI = (f"mongodb://{os.getenv('MONGO_USER','gridsense')}:"
             f"{os.getenv('MONGO_PASSWORD','gridsense_dev')}@localhost:27017")
PG = dict(host="localhost", port=5432, dbname=os.getenv("POSTGRES_DB", "gridsense"),
          user=os.getenv("POSTGRES_USER", "gridsense"),
          password=os.getenv("POSTGRES_PASSWORD", "gridsense_dev"))
RUNS = 10


def make_records():
    recs = []
    for i in range(10):
        recs.append({"asset_id": f"EQ_TX_{i:02d}", "type": "Transformer", "manufacturer": "ABB",
                     "firmware_version": f"{2 + i % 2}.{i}.0", "rated_voltage": 11000})
    for i in range(10):
        recs.append({"asset_id": f"EQ_SW_{i:02d}", "type": "Switchgear", "ip_rating": "IP54",
                     "firmware_version": f"3.{i}.1", "rated_voltage": 11000})
    for i in range(10):
        recs.append({"asset_id": f"EQ_SM_{i:02d}", "type": "SmartMeter",
                     "firmware_version": f"{2 + i % 2}.{i}.0",
                     "rated_voltage": 220 + i * 2, "tariff_class": "residential"})
    return recs


def time_query(fn):
    ts = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    return statistics.mean(ts)


def setup_mongo(records):
    client = MongoClient(MONGO_URI)
    coll = client["CatalogDB"]["equipment_c4"]
    coll.drop()
    coll.insert_many([dict(r) for r in records])   # copy so _id isn't added to originals
    return client, coll


def setup_postgres(records):
    conn = psycopg2.connect(**PG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS equipment_jsonb "
                "(asset_id TEXT PRIMARY KEY, metadata JSONB)")
    cur.execute("TRUNCATE equipment_jsonb")
    for r in records:
        cur.execute("INSERT INTO equipment_jsonb (asset_id, metadata) VALUES (%s, %s)",
                    (r["asset_id"], Json(r)))
    return conn, cur


def main():
    records = make_records()
    mclient, coll = setup_mongo(records)
    pconn, cur = setup_postgres(records)

    mongo_q = [
        lambda: list(coll.find({"firmware_version": {"$regex": "^3\\."}})),
        lambda: list(coll.find({"type": "SmartMeter", "rated_voltage": {"$gt": 230}})),
        lambda: list(coll.aggregate([{"$group": {"_id": "$type", "count": {"$sum": 1}}}])),
    ]

    def pg(sql):
        def run():
            cur.execute(sql)
            cur.fetchall()
        return run

    pg_q = [
        pg("SELECT asset_id FROM equipment_jsonb WHERE metadata->>'firmware_version' LIKE '3.%'"),
        pg("SELECT asset_id FROM equipment_jsonb WHERE metadata->>'type'='SmartMeter' "
           "AND (metadata->>'rated_voltage')::numeric > 230"),
        pg("SELECT metadata->>'type', count(*) FROM equipment_jsonb GROUP BY metadata->>'type'"),
    ]

    labels = ["1. firmware starts '3.'", "2. SmartMeter voltage>230", "3. count by type"]

    print(f"MongoDB vs PostgreSQL JSONB  (30 records, mean of {RUNS} runs, no indexes)\n")
    print(f"{'query':<28}{'Mongo ms':<12}{'Postgres ms':<12}")
    for label, mq, pq in zip(labels, mongo_q, pg_q):
        print(f"{label:<28}{time_query(mq):<12.3f}{time_query(pq):<12.3f}")

    mclient.close()
    pconn.close()


if __name__ == "__main__":
    main()