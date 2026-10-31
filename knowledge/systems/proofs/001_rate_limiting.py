"""Rate limiting. A runs against the real adapter (test fixture, fake agent); B compares the algorithms.
A. MAX_PENDING caps runs in flight; unsigned requests are rejected before they can use a slot; the daily cap holds.
B. Limit 10 requests per second. A client sends 10 at t=0.99 s and 10 more at t=1.01 s: 20 in 20 ms.
   A fixed window lets all 20 through; a sliding log and a token bucket hold the burst to the limit."""
import json
from collections import deque

from test_adapter import adapter, sign, trigger  # noqa: F401  (fixture)


def test_adapter_limits(adapter, monkeypatch):
    module, root, client = adapter
    monkeypatch.setenv("FAKE_SLEEP", "5")  # runs stay in flight while we send more
    codes = []
    for i in range(6):
        for _ in range(5):  # badly signed noise between valid requests
            client.post("/trigger", content=b'{"task": "x"}', headers={"X-Hub-Signature-256": "sha256=bad", "X-Factory-Timestamp": "1"})
        codes.append(trigger(client).status_code)
    print(f"\nA  6 valid triggers with 25 unsigned ones in between, MAX_PENDING=5: {codes}")


def test_daily_cap(adapter, monkeypatch):
    module, root, client = adapter
    monkeypatch.setattr(module, "MAX_PENDING", 100)
    monkeypatch.setattr(module, "MAX_RUNS_PER_DAY", 3)
    print(f"A  4 valid triggers, MAX_RUNS_PER_DAY=3: {[trigger(client).status_code for _ in range(4)]}")


def fixed_window(times, limit=10, size=1.0):
    counts, ok = {}, 0
    for t in times:
        w = int(t // size)
        if counts.get(w, 0) < limit:
            counts[w] = counts.get(w, 0) + 1
            ok += 1
    return ok


def sliding_log(times, limit=10, size=1.0):
    log, ok = deque(), 0
    for t in times:
        while log and log[0] <= t - size:
            log.popleft()
        if len(log) < limit:
            log.append(t)
            ok += 1
    return ok


def token_bucket(times, rate=10, burst=10):
    tokens, last, ok = burst, 0.0, 0
    for t in times:
        tokens = min(burst, tokens + (t - last) * rate)
        last = t
        if tokens >= 1:
            tokens -= 1
            ok += 1
    return ok


def test_algorithms():
    burst = [0.99 + i * 0.0001 for i in range(10)] + [1.01 + i * 0.0001 for i in range(10)]
    steady = [i * 0.1 for i in range(100)]  # exactly 10 a second for 10 s
    print("\nB  limit 10/s     20 sent in 20 ms across a window edge   100 sent evenly over 10 s")
    for name, fn in (("fixed window", fixed_window), ("sliding log", sliding_log), ("token bucket", token_bucket)):
        print(f"B  {name:<14}{fn(burst):>22} allowed{fn(steady):>30} allowed")
