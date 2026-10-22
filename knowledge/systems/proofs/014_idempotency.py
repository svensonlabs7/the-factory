"""Idempotency. A/B run against the real adapter (test fixture, fake agent); C/D are the fix in miniature.
A. A client retries the same task after a lost response: new timestamp, new signature -> a second run.
B. A client resends the exact same signed request: rejected as a replay, so it cannot learn its run_id.
C. An idempotency-key store returns the first response for a repeat, and rejects a reused key with new params.
D. Two requests with the same key at once: check-then-insert creates two; an atomic create creates one."""
import json
import os
import tempfile
import threading
import time
from pathlib import Path

from test_adapter import adapter, sign  # noqa: F401  (fixture)


def test_against_the_adapter(adapter):
    module, root, client = adapter
    body = json.dumps({"task": "Add a /version endpoint"}).encode()
    first = client.post("/trigger", content=body, headers=sign(body))
    time.sleep(1.1)  # the client's retry is signed a second later
    retry = client.post("/trigger", content=body, headers=sign(body))
    print(f"\nA  same task retried: {first.status_code} run {first.json()['run_id']}, "
          f"{retry.status_code} run {retry.json()['run_id']} -> two runs for one request")

    body2 = json.dumps({"task": "Add a /ping endpoint"}).encode()
    headers = sign(body2)
    ok = client.post("/trigger", content=body2, headers=headers)
    again = client.post("/trigger", content=body2, headers=headers)
    print(f"B  exact resend: {ok.status_code} run {ok.json()['run_id']}, then {again.status_code} {again.json()}")


class Store:
    def __init__(self, atomic):
        self.dir = Path(tempfile.mkdtemp())
        self.atomic = atomic
        self.created = []

    def create_run(self, key, params):
        record = self.dir / key
        if self.atomic:
            try:
                fd = os.open(record, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                return self.replay(record, params)
            run_id = f"run{len(self.created) + 1}"
            self.created.append(run_id)
            os.write(fd, json.dumps({"params": params, "response": {"run_id": run_id}}).encode())
            os.close(fd)
            return 202, {"run_id": run_id}
        if record.exists():
            return self.replay(record, params)
        time.sleep(0.01)  # the gap between the check and the write, where a concurrent request slips in
        run_id = f"run{len(self.created) + 1}"
        self.created.append(run_id)
        record.write_text(json.dumps({"params": params, "response": {"run_id": run_id}}))
        return 202, {"run_id": run_id}

    def replay(self, record, params):
        for _ in range(100):  # the first request may still be writing its record
            text = record.read_text()
            if text:
                break
            time.sleep(0.001)
        saved = json.loads(text)
        if saved["params"] != params:
            return 422, {"detail": "idempotency key reused with different parameters"}
        return 200, saved["response"]


def test_the_fix():
    s = Store(atomic=True)
    print(f"\nC  first:          {s.create_run('k1', {'task': 'version'})}")
    print(f"C  retry same key: {s.create_run('k1', {'task': 'version'})}")
    print(f"C  same key, new task: {s.create_run('k1', {'task': 'ping'})}")
    print(f"C  runs created: {s.created}")
    for atomic in (False, True):
        s = Store(atomic)
        threads = [threading.Thread(target=s.create_run, args=("k2", {"task": "version"})) for _ in range(5)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        print(f"D  5 concurrent requests, one key, {'atomic create  ' if atomic else 'check-then-write'}: runs created {len(s.created)}")
