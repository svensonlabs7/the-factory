"""Latency.
A. A measured latency ladder on this host, for the operations the factory actually performs (medians).
   The public hostname is probed without credentials, so Cloudflare Access answers 401 at its edge: that is the edge
   round trip, not the full path to the adapter.
B. Errors are fast: a service whose normal requests take 120 ms has 30% of them fail in 2 ms. The overall mean
   improves while users are failing; split by outcome, it does not."""
import os
import socket
import statistics
import subprocess
import tempfile
import time
import timeit

import httpx


def med(fn, n):
    samples = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1e3)
    return statistics.median(samples)


rows = []
rows.append(("Python function call", timeit.timeit("f()", "f = lambda: None", number=100_000) / 100_000 * 1e3))
path = tempfile.mktemp()
with open(path, "w") as f:
    f.write("x" * 4096)
rows.append(("read a 4 KB file", med(lambda: open(path).read(), 200)))


def fsync_write():
    with open(path, "w") as f:
        f.write("x" * 4096)
        f.flush()
        os.fsync(f.fileno())


rows.append(("write + fsync a 4 KB file", med(fsync_write, 50)))
with httpx.Client() as c:
    rows.append(("GET /health, live adapter on localhost (keep-alive)", med(lambda: c.get("http://127.0.0.1:7654/health"), 100)))
rows.append(("DNS lookup factory.svensonlabs.dev", med(lambda: socket.getaddrinfo("factory.svensonlabs.dev", 443), 5)))
rows.append(("HTTPS to Cloudflare edge, new connection (Access 401)", med(lambda: httpx.get("https://factory.svensonlabs.dev/health"), 8)))
with httpx.Client() as c:
    c.get("https://factory.svensonlabs.dev/health")
    rows.append(("HTTPS to Cloudflare edge, reused connection", med(lambda: c.get("https://factory.svensonlabs.dev/health"), 8)))
rows.append(("gh api rate_limit (process + TLS + GitHub)", med(lambda: subprocess.run(["gh", "api", "rate_limit"], capture_output=True), 5)))
status = httpx.get("https://factory.svensonlabs.dev/health").status_code
for name, ms in rows:
    print(f"A  {name:<55} {ms:10.4f} ms")
print(f"A  (edge answered {status} without credentials)")

ok, err = 120.0, 2.0
before = ok
during = 0.7 * ok + 0.3 * err
print(f"B  mean latency, healthy: {before:.0f} ms; during an outage failing 30% fast: {during:.0f} ms (looks better)")
print(f"B  split by outcome during the outage: success {ok:.0f} ms, error {err:.0f} ms, error rate 30%")
