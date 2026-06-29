# warm batch: 500 GETs on one primed sensor  -> cache HITS.
# cold batch: 500 GETs on unique sensor ids   -> guaranteed MISSES.
# Hit/miss verified via the endpoint's own `cached` flag.
import json
import statistics
import time
import urllib.request

BASE = "http://localhost:8000"
WARM_SENSOR = "S_000"
N = 500


def get_summary(sensor):
    t0 = time.perf_counter()
    with urllib.request.urlopen(f"{BASE}/sensors/{sensor}/summary") as r:
        data = json.loads(r.read())
    return (time.perf_counter() - t0) * 1000, bool(data.get("cached"))


def pctl(s, p):
    if len(s) < 2:
        return float("nan")
    return statistics.quantiles(s, n=100, method="inclusive")[p - 1]


def main():
    get_summary(WARM_SENSOR)   # prime the cache for the warm batch

    warm_lat, warm_hits = [], 0
    for _ in range(N):
        ms, cached = get_summary(WARM_SENSOR)
        warm_lat.append(ms)
        warm_hits += cached

    cold_lat, cold_hits = [], 0
    for i in range(N):
        ms, cached = get_summary(f"S_COLD_{i}")
        cold_lat.append(ms)
        cold_hits += cached

    print("Redis cache effectiveness  (/sensors/{id}/summary)")
    print(f"method: {N} warm (cache hits, one primed sensor) + {N} cold "
          f"(cache misses, unique sensor ids) hit/miss from the `cached` flag\n")
    print(f"{'batch':<8}{'hit rate':<10}{'p50 ms':<10}{'p95 ms':<10}{'p99 ms':<10}")
    print(f"{'warm':<8}{warm_hits / N:<10.0%}{pctl(warm_lat, 50):<10.2f}"
          f"{pctl(warm_lat, 95):<10.2f}{pctl(warm_lat, 99):<10.2f}")
    print(f"{'cold':<8}{cold_hits / N:<10.0%}{pctl(cold_lat, 50):<10.2f}"
          f"{pctl(cold_lat, 95):<10.2f}{pctl(cold_lat, 99):<10.2f}")

    overall = (warm_hits + cold_hits) / (2 * N)
    print(f"\noverall hit rate (1000 reqs): {overall:.0%}")
    print(f"cache speedup at p50: {pctl(cold_lat, 50) / pctl(warm_lat, 50):.1f}x "
          f"(miss {pctl(cold_lat, 50):.2f} ms vs hit {pctl(warm_lat, 50):.2f} ms)")


if __name__ == "__main__":
    main()