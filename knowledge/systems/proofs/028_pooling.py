"""Connection pooling.
A. Real TLS to api.github.com (GET /rate_limit, which GitHub does not count against the limit): a new connection
   per request vs one pooled keep-alive client, 10 requests each.
B. SQLAlchemy's QueuePool (pool_size 5, max_overflow 0, pool_timeout 1 s) on a SQLite file: 20 threads each hold a
   connection for 0.3 s; then a leak (connections checked out and never returned).
C. What one `gh` call costs before any network: process start (`gh --version`), vs a full `gh api rate_limit`."""
import statistics
import subprocess
import tempfile
import threading
import time

import httpx
from sqlalchemy import create_engine, exc, text

URL = "https://api.github.com/rate_limit"


def timed(fn):
    t = time.perf_counter()
    fn()
    return (time.perf_counter() - t) * 1e3


fresh = [timed(lambda: httpx.Client().get(URL).raise_for_status()) for _ in range(10)]
with httpx.Client() as client:
    pooled = [timed(lambda: client.get(URL).raise_for_status()) for _ in range(10)]
print(f"A  new connection per request: median {statistics.median(fresh):6.1f} ms")
print(f"A  pooled keep-alive client:   median {statistics.median(pooled[1:]):6.1f} ms (first request {pooled[0]:.1f} ms opens the connection)")

engine = create_engine(f"sqlite:///{tempfile.mktemp()}", pool_size=5, max_overflow=0, pool_timeout=1)
ok, timeouts, waits = [0], [0], []


def request():
    t = time.perf_counter()
    try:
        with engine.connect() as conn:
            waits.append(time.perf_counter() - t)
            conn.execute(text("SELECT 1"))
            time.sleep(0.3)
        ok[0] += 1
    except exc.TimeoutError:
        timeouts[0] += 1


threads = [threading.Thread(target=request) for _ in range(20)]
[t.start() for t in threads]
[t.join() for t in threads]
print(f"B  20 concurrent, pool 5, hold 0.3 s: {ok[0]} served, {timeouts[0]} timed out; max wait for a connection {max(waits):.2f} s")

leaked = [engine.connect() for _ in range(5)]  # checked out, never closed
ok[0] = timeouts[0] = 0
request()
print(f"B  after 5 leaked connections: next request -> {'served' if ok[0] else 'TimeoutError (QueuePool limit of size 5 overflow 0 reached)'}")
for c in leaked:
    c.close()

spawn = statistics.median(timed(lambda: subprocess.run(["gh", "--version"], capture_output=True)) for _ in range(5))
full = statistics.median(timed(lambda: subprocess.run(["gh", "api", "rate_limit"], capture_output=True)) for _ in range(5))
print(f"C  gh --version (process start only): {spawn:6.1f} ms; gh api rate_limit (start + new TLS + request): {full:6.1f} ms")
