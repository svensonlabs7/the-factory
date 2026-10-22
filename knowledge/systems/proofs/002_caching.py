"""Caching.
A. Cache-aside LRU in front of a 50 ms backend, Zipf-distributed reads over 10,000 keys (seeded): hit ratio and mean
   latency by cache size, and the modal effect of a cold cache (backend calls in the first 1,000 vs a later 1,000).
B. Stampede: 50 threads miss the same key at once. Plain cache-aside calls the backend 50 times; request coalescing
   (one in-flight load per key) calls it once. Real threads, a 100 ms backend.
C. The factory's `_pr` cache (real function via tests/test_adapter.py's fixture): an OPEN PR's entry is past its TTL
   and the refresh fails. Hard expiry drops the data; a soft TTL would keep serving the stale entry."""
import json
import random
import threading
import time
from collections import OrderedDict

from test_adapter import adapter  # noqa: F401  (fixture)


def zipf_keys(n, keys=10_000, s=1.1, seed=2):
    rng = random.Random(seed)
    weights = [1 / (i + 1) ** s for i in range(keys)]
    return rng.choices(range(keys), weights=weights, k=n)


def test_hit_ratio():
    reqs = zipf_keys(20_000)
    for size in (10, 100, 1000):
        cache, hits, first, later = OrderedDict(), 0, 0, 0
        for i, k in enumerate(reqs):
            if k in cache:
                cache.move_to_end(k)
                hits += 1
                continue
            if i < 1000:
                first += 1
            elif 10_000 <= i < 11_000:
                later += 1
            cache[k] = True
            if len(cache) > size:
                cache.popitem(last=False)
        ratio = hits / len(reqs)
        print(f"{chr(10) if size == 10 else ''}A  LRU size {size:>5}: hit ratio {ratio:5.1%}, mean latency {(1 - ratio) * 50:5.1f} ms; backend calls: first 1,000 requests {first}, a later 1,000 {later}")


def test_stampede():
    for coalesce in (False, True):
        calls, cache, inflight, lock = [0], {}, {}, threading.Lock()

        def backend():
            calls[0] += 1
            time.sleep(0.1)
            return "value"

        def get():
            if "k" in cache:
                return cache["k"]
            if not coalesce:
                cache["k"] = backend()
                return cache["k"]
            with lock:
                event = inflight.get("k")
                leader = event is None
                if leader:
                    event = inflight["k"] = threading.Event()
            if leader:
                cache["k"] = backend()
                event.set()
            else:
                event.wait()
            return cache["k"]

        threads = [threading.Thread(target=get) for _ in range(50)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        print(f"B  50 concurrent misses, {'request coalescing' if coalesce else 'plain cache-aside '}: backend called {calls[0]} times")


def test_pr_soft_ttl(adapter, monkeypatch):
    module, root, client = adapter
    url = "https://github.com/o/r/pull/3"
    module._pr_cache[url] = (time.time() - 3600, {"state": "OPEN", "checks": [{"name": "tests", "result": "pass"}]})

    def broken(*cmd, cwd=None):
        raise RuntimeError("gh: HTTP 502 Bad Gateway")

    monkeypatch.setattr(module, "_run", broken)
    print(f"C  OPEN PR cached an hour ago, refresh fails: _pr returns {module._pr(url)} (the cached state is dropped, not served stale)")
