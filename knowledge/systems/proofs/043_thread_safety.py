"""Thread safety.
A. `n += 1` is not atomic even with the GIL (load, add, store): 8 threads x 200,000 increments, with a tiny switch interval.
B. The adapter's real _pr cache (test fixture), called by 8 threads at once for one PR URL: each dict op is atomic,
   but check-cache, then fetch, then store is not, so every thread misses and calls `gh`. Benign duplicate work, not corruption."""
import sys
import threading
import time

from test_adapter import adapter  # noqa: F401  (fixture)


def test_plus_equals():
    sys.setswitchinterval(1e-6)
    n = 0

    def work():
        nonlocal n
        for _ in range(200_000):
            n += 1
    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    sys.setswitchinterval(0.005)
    print(f"\nA  8 threads x 200,000 `n += 1`: n = {n:,} (expected 1,600,000; lost {1_600_000 - n:,})")


def test_pr_cache_stampede(adapter, monkeypatch):
    module, root, client = adapter
    calls = []

    def fake_run(*cmd, **kw):
        calls.append(cmd)
        time.sleep(0.2)  # a gh round trip
        return '{"state": "OPEN", "statusCheckRollup": []}'
    monkeypatch.setattr(module, "_run", fake_run)
    module._pr_cache.clear()
    url = "https://github.com/x/y/pull/1"
    ts = [threading.Thread(target=module._pr, args=(url,)) for _ in range(8)]
    t = time.time()
    [x.start() for x in ts]
    [x.join() for x in ts]
    print(f"B  8 concurrent _pr() for one URL, cold cache: gh called {len(calls)} times in {time.time() - t:.1f} s; cached after: {url in module._pr_cache}")
    calls.clear()
    module._pr(url)
    print(f"B  a 9th call right after: gh called {len(calls)} times (cache hit)")
