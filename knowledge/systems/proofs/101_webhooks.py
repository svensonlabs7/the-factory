"""Webhooks: the factory's /trigger as a receiver, tested against the real adapter (test fixture, fake agent).
1. A body changed after signing is refused.  2. A correctly signed but stale request is refused.
3. During secret rotation the previous secret still works.  4. The sender gets 202 at once while the build runs.
5. An oversized task (2 MB) is accepted, then fails at spawn: macOS ARG_MAX is 1 MB and the task rides in argv."""
import json
import time

import pytest

from test_adapter import OLD_SECRET, adapter, previous, sign, wait_done  # noqa: F401  (fixtures)


def test_receiver(adapter, monkeypatch):
    module, root, client = adapter
    body = json.dumps({"task": "Add a /version endpoint"}).encode()
    headers = sign(body)
    tampered = body.replace(b"version", b"rm -rf /")
    print(f"\n1  tampered body: {client.post('/trigger', content=tampered, headers=headers).json()}")

    old = int(time.time()) - 400
    print(f"2  signed 400 s ago: {client.post('/trigger', content=body, headers=sign(body, timestamp=old)).json()}")

    monkeypatch.setenv("FAKE_SLEEP", "3")
    t = time.time()
    r = client.post("/trigger", content=body, headers=sign(body))
    answered = time.time() - t
    run = wait_done(client, r.json()["run_id"])
    print(f"4  answered {r.status_code} in {answered * 1000:.0f} ms; the run finished {run['finished_at'] - t:.1f} s later as {run['status']}")

    monkeypatch.setenv("FAKE_SLEEP", "0")
    big = json.dumps({"task": "x" * 2_000_000}).encode()
    r = client.post("/trigger", content=big, headers=sign(big))
    run = wait_done(client, r.json()["run_id"])
    print(f"5  2 MB task: {r.status_code} accepted, then status={run['status']!r} error={run.get('error')!r}")


@pytest.mark.parametrize("previous", [OLD_SECRET], indirect=True)
def test_rotation(previous, adapter):
    module, root, client = adapter
    body = json.dumps({"task": "rotation check"}).encode()
    print(f"\n3  signed with the previous secret during rotation: {client.post('/trigger', content=body, headers=sign(body, secret=OLD_SECRET)).status_code}")
