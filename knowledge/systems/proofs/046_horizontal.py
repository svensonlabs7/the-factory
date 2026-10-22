"""Horizontal scaling.
A. State that does not scale out: the adapter keeps its rejection-burst counter in process memory. 30 bad-signature
   requests to one adapter open the HEARTBEAT incident (threshold 20); the same 30 split across two copies behind a
   round-robin balancer open nothing. Real module, imported twice (tests/test_adapter.py's fixture).
B. Coordination limits scale-out (USL): N processes each increment a shared counter guarded by an exclusive file lock,
   for 2 s. Throughput in total increments per second, vs N."""
import fcntl
import importlib
import json
import os
import sys
import tempfile
import time
from multiprocessing import Process, Value

from fastapi.testclient import TestClient

from test_adapter import adapter  # noqa: F401  (fixture)


def bad(client, i):
    body = json.dumps({"task": f"x{i}"}).encode()
    return client.post("/trigger", content=body, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64, "X-Factory-Timestamp": str(int(time.time()))})


def incidents(root):
    return [l for l in (root / "HEARTBEAT.md").read_text().splitlines() if "open_incidents" in l][0].split("|")[2].strip()


def test_split_state(adapter):
    one, root, c1 = adapter
    for i in range(30):
        bad(c1, i)
    single = incidents(root)
    one._set_heartbeat(open_incidents="none")
    one._recent_rejections.clear()
    one._burst_open = False
    sys.modules.pop("factory.intake.webhook_adapter", None)
    two = importlib.import_module("factory.intake.webhook_adapter")   # a second copy, same shared files
    c2 = TestClient(two.app)
    for i in range(30):
        bad(c1 if i % 2 == 0 else c2, 100 + i)
    split = incidents(root)
    print(f"\nA  30 bad requests, one adapter:            open_incidents = {single!r}")
    print(f"A  30 bad requests, two adapters round-robin: open_incidents = {split!r} (each copy counted {len(one._recent_rejections)} and {len(two._recent_rejections)})")
    two.RUN_EXECUTOR.shutdown(wait=True)


def worker(path, counter, stop_at):
    while time.time() < stop_at:
        with open(path, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            n = int(f.read() or 0)
            f.seek(0)
            f.write(str(n + 1))
            f.truncate()
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
        with counter.get_lock():
            counter.value += 1


def test_shared_lock_scaling():
    for n in (1, 2, 4, 8):
        path = tempfile.mktemp()
        open(path, "w").write("0")
        counter = Value("i", 0)
        stop_at = time.time() + 2
        procs = [Process(target=worker, args=(path, counter, stop_at)) for _ in range(n)]
        [p.start() for p in procs]
        [p.join() for p in procs]
        print(f"B  {n} processes sharing one locked counter: {counter.value / 2:8.0f} increments/s")
