"""Dead letter queues.
A. Simulation: 20 messages in a FIFO queue, the 3rd is poison (its handler always crashes). Redelivering forever
   blocks everything behind it; maxReceiveCount=3 parks it in a DLQ and the rest flow. Redrive after a fix drains it.
B. The real adapter (test fixture, fake agent): a run that was in flight when the service died is parked as
   `error`, not requeued; and a failed run followed by a good one leaves HEARTBEAT looking healthy."""
import importlib
import json
import sys
from collections import deque

from test_adapter import adapter, trigger, wait_done  # noqa: F401  (fixture)


def drain(max_receives, handler_fixed=False, budget=200):
    q = deque((i, 0) for i in range(20))
    dlq, done, receives = [], [], 0
    while q and receives < budget:
        msg, count = q.popleft()
        receives += 1
        if msg == 2 and not handler_fixed:  # poison
            count += 1
            if max_receives and count >= max_receives:
                dlq.append(msg)
            else:
                q.appendleft((msg, count))  # FIFO: it comes straight back to the head
            continue
        done.append(msg)
    return done, dlq, receives, q


def test_simulation():
    done, dlq, receives, left = drain(max_receives=None)
    print(f"\nA  no DLQ:            processed {len(done)}/19 good, {receives} receives used, {len(left)} still queued")
    done, dlq, receives, left = drain(max_receives=3)
    print(f"A  maxReceiveCount=3: processed {len(done)}/19 good, {receives} receives used, DLQ={dlq}  -> alarm: 1 dead message")
    def redrive(fixed):
        processed, dead = [], []
        for msg in dlq:  # move each dead message back and run it through the same handler
            for attempt in range(1, 4):
                if msg != 2 or fixed:
                    processed.append(msg)
                    break
            else:
                dead.append(msg)
        return processed, dead
    print(f"A  redrive, no fix:   processed {redrive(False)[0]}, back in DLQ {redrive(False)[1]}")
    print(f"A  redrive after fix: processed {redrive(True)[0]}, back in DLQ {redrive(True)[1]}")


def test_adapter_dead_runs(adapter, monkeypatch):
    module, root, client = adapter
    monkeypatch.setenv("FAKE_EXIT", "1")
    bad = wait_done(client, trigger(client).json()["run_id"])
    hb_after_bad = client.get("/heartbeat").json()
    monkeypatch.setenv("FAKE_EXIT", "0")
    good = wait_done(client, trigger(client).json()["run_id"])
    hb_after_good = client.get("/heartbeat").json()
    print(f"\nB  run {bad['run_id']}: {bad['status']} -> heartbeat pipeline_status={hb_after_bad['pipeline_status']!r}")
    print(f"B  run {good['run_id']}: {good['status']} -> heartbeat pipeline_status={hb_after_good['pipeline_status']!r} "
          f"blocking_reason={hb_after_good['blocking_reason']!r}; the failed run is still on disk: "
          f"{client.get('/status/' + bad['run_id']).json()['status']}")

    # A run that was mid-flight when the service died, then the service restarts.
    (root / ".factory-logs" / "crashed1.meta.json").write_text(json.dumps({"run_id": "crashed1", "status": "running", "task": "t"}))
    module.RUN_EXECUTOR.shutdown(wait=True)
    sys.modules.pop("factory.intake.webhook_adapter")
    restarted = importlib.import_module("factory.intake.webhook_adapter")
    after = json.loads((root / ".factory-logs" / "crashed1.meta.json").read_text())
    print(f"B  in-flight run after restart: status={after['status']!r} error={after.get('error')!r} (parked, not requeued)")
    restarted.RUN_EXECUTOR.shutdown(wait=True)
