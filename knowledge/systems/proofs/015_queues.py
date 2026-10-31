"""Message queues: delivery guarantees across a crash, with the adapter's real queue (tests/test_adapter.py's fixture).
The adapter's queue is RUN_EXECUTOR's in-memory work queue (one worker) plus a "queued" meta record per run.
A. Three runs accepted (one building, two waiting), then the process dies: the in-memory queue is lost, and the
   restart's _recover closes all three as error, including the two that never started (at-most-once).
B. The same crash, but on restart the never-started runs are put back on the queue from their meta records
   (task and branch are on disk), as a durable queue with ack-after-processing would redeliver them."""
import importlib
import sys
import time

from test_adapter import adapter, trigger, wait_done  # noqa: F401  (fixture)


def accept_three_then_crash(module, client, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "1")
    ids = [trigger(client).json()["run_id"] for _ in range(3)]
    for _ in range(100):
        if client.get(f"/status/{ids[0]}").json()["status"] == "running":
            break
        time.sleep(0.02)
    before = {r: module._load(r)["status"] for r in ids}
    module.RUN_EXECUTOR.shutdown(wait=False, cancel_futures=True)  # the process dies: the in-memory queue is gone
    return ids, before


def restart():
    sys.modules.pop("factory.intake.webhook_adapter", None)
    module = importlib.import_module("factory.intake.webhook_adapter")
    module.CHECKS_POLL = 0
    return module


def test_at_most_once(adapter, monkeypatch):
    module, root, client = adapter
    ids, before = accept_three_then_crash(module, client, monkeypatch)
    new = restart()
    after = {r: (new._load(r)["status"], "started" if "started_at" in new._load(r) else "never started") for r in ids}
    print(f"\nA  at the crash: {before}")
    print(f"A  after restart: {after}")
    time.sleep(1.5)
    new.RUN_EXECUTOR.shutdown(wait=True)


def test_redeliver_queued(adapter, monkeypatch):
    module, root, client = adapter
    ids, before = accept_three_then_crash(module, client, monkeypatch)
    waiting = [r for r in ids if before[r] == "queued"]
    for r in waiting:  # stands in for a _recover that tells never-started runs from started ones
        module._update(r, status="pending-redelivery")
    new = restart()
    for r in waiting:
        run = new._load(r)
        new._update(r, status="queued")
        new.RUN_EXECUTOR.submit(new._run_agent, r, new._build_prompt(run["task"], run["branch"], r), run["branch"])
    from fastapi.testclient import TestClient
    c = TestClient(new.app)
    print(f"B  never-started runs put back on the queue: {[ (r, wait_done(c, r)['status']) for r in waiting]}")
    new.RUN_EXECUTOR.shutdown(wait=True)
