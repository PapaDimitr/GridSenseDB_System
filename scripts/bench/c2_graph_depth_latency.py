# Sequential GETs (clean per-request latency). 50 iters/depth, first 3 discarded as warmup.
# Run:  python scripts/bench/c2_graph_depth_latency.py
import csv
import json
import statistics
import time
import urllib.request

BASE_URL = "http://localhost:8000"
NODE = "GSP_NORTH"        # 10 subs 40 transformers 200 meters // 250 downstream, 3 deep
DEPTHS = range(1, 9)      # max_depth 1..8
ITERATIONS = 50           # timed requests per depth (>= 30 required)
WARMUP = 3                # discarded per depth
OUT_CSV = "scripts/bench/c2_results.csv"


def pctl(s, p):
    if len(s) < 2:
        return float("nan")
    return statistics.quantiles(s, n=100, method="inclusive")[p - 1]


def call(depth):
    url = f"{BASE_URL}/grid/fault-impact/{NODE}?max_depth={depth}"
    t0 = time.perf_counter()
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    return (time.perf_counter() - t0) * 1000, data.get("total_affected", -1)


def main():
    print(f"Graph traversal depth vs latency  (node={NODE}, "
          f"{ITERATIONS} iters/depth, {WARMUP} warmup discarded)\n")
    print(f"{'depth':<7}{'affected':<10}{'p50 ms':<10}{'p95 ms':<10}")
    rows = []
    for d in DEPTHS:
        for _ in range(WARMUP):
            call(d)
        lat, affected = [], -1
        for _ in range(ITERATIONS):
            ms, affected = call(d)
            lat.append(ms)
        p50, p95 = pctl(lat, 50), pctl(lat, 95)
        print(f"{d:<7}{affected:<10}{p50:<10.2f}{p95:<10.2f}")
        rows.append((d, affected, round(p50, 3), round(p95, 3)))

    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["depth", "affected", "p50_ms", "p95_ms"])
        w.writerows(rows)
    print(f"\nwrote {OUT_CSV} (depth, affected, p50_ms, p95_ms) for the line chart")


if __name__ == "__main__":
    main()
