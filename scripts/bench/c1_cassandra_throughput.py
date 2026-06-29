# Throughput is measured in INTERLEAVED rounds (CL order rotates each round) so a
# real consistency-level effect can be separated from a fixed test-order effect.
# Latency: sequential per level.
import statistics
import time
from datetime import datetime, timedelta, timezone

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args

CONTACT_POINTS = ["localhost"]
KEYSPACE = "gridsense"
LATENCY_SAMPLES = 2000        # sequential writes per level
THROUGHPUT_WRITES = 10000     # concurrent writes per round
ROUNDS = 9                    # throughput rounds, CL order rotates each round
CONCURRENCY = 64
LEVELS = [("ONE", ConsistencyLevel.ONE),
          ("LOCAL_QUORUM", ConsistencyLevel.LOCAL_QUORUM),
          ("ALL", ConsistencyLevel.ALL)]

_n = 0


def pctl(s, p):
    if len(s) < 2:
        return float("nan")
    return statistics.quantiles(s, n=100, method="inclusive")[p - 1]


def make_rows(base, k):
    global _n
    out = []
    for _ in range(k):
        _n += 1
        out.append((f"BENCH_{_n % 50}", base + timedelta(milliseconds=_n),
                    "voltage", 230.0, "V", 0))
    return out


def main():
    cluster = Cluster(CONTACT_POINTS)
    session = cluster.connect(KEYSPACE)
    insert = session.prepare(
        "INSERT INTO sensor_readings "
        "(sensor_id, reading_time, metric_type, value, unit, quality_flag) "
        "VALUES (?, ?, ?, ?, ?, ?)")
    base = datetime(2030, 1, 1, tzinfo=timezone.utc)

    print("Cassandra write throughput vs consistency level (single-node, RF=1)")
    print(f"method: latency = {LATENCY_SAMPLES} sequential writes/level "
          f"throughput = {ROUNDS} interleaved rounds x {THROUGHPUT_WRITES} concurrent "
          f"writes/level (concurrency={CONCURRENCY}); CL order rotates each round\n")

    # latency — sequential, one pass per level
    lat = {name: [] for name, _ in LEVELS}
    for name, cl in LEVELS:
        insert.consistency_level = cl
        for _ in range(LATENCY_SAMPLES):
            row = make_rows(base, 1)[0]
            t0 = time.perf_counter()
            session.execute(insert, row)
            lat[name].append((time.perf_counter() - t0) * 1000)

    # throughput — interleaved rounds with rotating order
    tput = {name: [] for name, _ in LEVELS}
    errors = 0
    for rnd in range(ROUNDS):
        shift = rnd % len(LEVELS)
        order = LEVELS[shift:] + LEVELS[:shift]   # rotate so each CL hits each position
        for name, cl in order:
            insert.consistency_level = cl
            batch = make_rows(base, THROUGHPUT_WRITES)
            t0 = time.perf_counter()
            res = execute_concurrent_with_args(session, insert, batch,
                                               concurrency=CONCURRENCY,
                                               raise_on_first_error=False)
            dt = time.perf_counter() - t0
            errors += sum(1 for ok, _ in res if not ok)
            tput[name].append(THROUGHPUT_WRITES / dt)

    print(f"{'CL':<14}{'ev/s mean':<11}{'stdev':<8}{'min':<8}{'max':<8}"
          f"{'p50 ms':<9}{'p95 ms':<9}")
    for name, _ in LEVELS:
        s = tput[name]
        print(f"{name:<14}{statistics.mean(s):<11.0f}{statistics.pstdev(s):<8.0f}"
              f"{min(s):<8.0f}{max(s):<8.0f}{pctl(lat[name], 50):<9.3f}"
              f"{pctl(lat[name], 95):<9.3f}")
    print("\nraw events/s samples")
    for name, _ in LEVELS:
        print(f"  {name:<14}{[round(x) for x in tput[name]]}")
    print(f"\ntotal errors: {errors}")
    cluster.shutdown()


if __name__ == "__main__":
    main()