# realistic hit rate under cache eviction: allkeys-lru vs allkeys-lfu.
import json
import random
import subprocess
import urllib.request

BASE = "http://localhost:8000"
REDIS_CONTAINER = "gridsense_redis"
REDIS_PW = "gridsense_dev"           # dev password from .env
HOT = [f"S_{i:03d}" for i in range(20)]   # 20 hot (seeded) sensors
N_REQUESTS = 10000
HOT_FRACTION = 0.5                   # 50% of traffic to the hot set, 50% one-hit-wonders
DATA_BUDGET = 1_000_000              # bytes of cached data allowed above baseline before eviction


def redis_cli(*args):
    out = subprocess.run(
        ["docker", "exec", REDIS_CONTAINER, "redis-cli", "-a", REDIS_PW, *args],
        capture_output=True, text=True)
    return out.stdout.strip()


def info_int(section, key):
    for line in redis_cli("info", section).splitlines():
        if line.startswith(key + ":"):
            return int(line.split(":")[1])
    return 0


def build_stream():
    random.seed(0)
    stream, cold = [], 0
    for _ in range(N_REQUESTS):
        if random.random() < HOT_FRACTION:
            stream.append(random.choice(HOT))          # hot key (repeats)
        else:
            stream.append(f"S_COLD_{cold}")            # one-hit-wonder
            cold += 1
    return stream


def get_cached(sensor):
    try:
        with urllib.request.urlopen(f"{BASE}/sensors/{sensor}/summary") as resp:
            return bool(json.loads(resp.read()).get("cached"))
    except Exception:
        return False   # a failed request can't be a cache hit


def run_policy(policy, stream):
    redis_cli("flushdb")
    baseline = info_int("memory", "used_memory")
    redis_cli("config", "set", "maxmemory", str(baseline + DATA_BUDGET))
    redis_cli("config", "set", "maxmemory-policy", policy)
    before = info_int("stats", "evicted_keys")
    hits = sum(get_cached(s) for s in stream)
    return hits / len(stream), info_int("stats", "evicted_keys") - before


def main():
    stream = build_stream()   # identical stream for both policies (fair comparison)
    print("C.3b  realistic hit rate under eviction: allkeys-lru vs allkeys-lfu")
    print(f"method: {N_REQUESTS} requests, {int(HOT_FRACTION*100)}% to {len(HOT)} hot sensors "
          f"+ {int((1-HOT_FRACTION)*100)}% one-hit-wonders; maxmemory = baseline + "
          f"{DATA_BUDGET // 1000}kb; identical stream per policy\n")
    print(f"{'policy':<16}{'hit rate':<12}{'evicted keys':<14}")
    for pol in ("allkeys-lru", "allkeys-lfu"):
        hr, ev = run_policy(pol, stream)
        print(f"{pol:<16}{hr:<12.1%}{ev:<14}")

    redis_cli("config", "set", "maxmemory", "256mb")          # restore
    redis_cli("config", "set", "maxmemory-policy", "allkeys-lru")
    print("\n(restored maxmemory=256mb, policy=allkeys-lru)")

if __name__ == "__main__":
    main()