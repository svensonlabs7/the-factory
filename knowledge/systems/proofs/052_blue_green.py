"""Blue-green deployment of the adapter: start "green" next to a live "blue" and switch traffic to it.
Blue and green are two imports of the real adapter module (tests/test_adapter.py's fixture, fake agent and gh).
A. Shared state: green uses blue's FACTORY_ROOT, as a second copy of the plist would.
B. Separate state: green gets its own root, and blue drains its run before it is stopped."""
import importlib
import sys
import time

from test_adapter import adapter, trigger, wait_done  # noqa: F401  (fixture)
from fastapi.testclient import TestClient


def start_green():
    sys.modules.pop("factory.intake.webhook_adapter", None)
    green = importlib.import_module("factory.intake.webhook_adapter")
    green.CHECKS_POLL = 0
    return green, TestClient(green.app)


def wait_status(client, run_id, status):
    for _ in range(100):
        if client.get(f"/status/{run_id}").json()["status"] == status:
            return
        time.sleep(0.05)


def test_shared_state(adapter, monkeypatch):
    blue, root, blue_client = adapter
    monkeypatch.setenv("FAKE_SLEEP", "2")
    run_id = trigger(blue_client).json()["run_id"]
    wait_status(blue_client, run_id, "running")
    green, green_client = start_green()   # its import runs _recover on the shared run records
    seen = green_client.get(f"/status/{run_id}").json()
    print(f"\nA  green starts while blue builds {run_id}: green reports {seen['status']!r} ({seen.get('error')})")
    second = trigger(green_client).json()["run_id"]
    wait_status(green_client, second, "running")
    blue_busy = blue.RUN_EXECUTOR._work_queue.qsize() > 0 or any(t.is_alive() for t in blue.RUN_EXECUTOR._threads)
    print(f"A  green accepts a new run while blue's worker is still building: blue worker alive {blue_busy}, green's run {green_client.get(f'/status/{second}').json()['status']!r}, green counts in flight {green._capacity(green._runs())[0]}")
    blue.RUN_EXECUTOR.shutdown(wait=True)
    final = blue_client.get(f"/status/{run_id}").json()
    events = [e["event"] for e in map(__import__("json").loads, blue._actions_log(run_id).read_text().splitlines())]
    print(f"A  after blue's worker ends: record {final['status']!r}, blue's own events for it: {events}")
    wait_done(green_client, second)
    green.RUN_EXECUTOR.shutdown(wait=True)


def test_separate_state(adapter, monkeypatch, tmp_path):
    blue, root, blue_client = adapter
    monkeypatch.setenv("FAKE_SLEEP", "2")
    run_id = trigger(blue_client).json()["run_id"]
    wait_status(blue_client, run_id, "running")
    green_root = tmp_path / "green"
    green_root.mkdir()
    (green_root / "HEARTBEAT.template.md").write_text((root / "HEARTBEAT.md").read_text())
    monkeypatch.setenv("FACTORY_ROOT", str(green_root))
    green, green_client = start_green()
    seen = blue_client.get(f"/status/{run_id}").json()["status"]
    final = wait_done(blue_client, run_id)["status"]   # drain blue before stopping it
    print(f"B  green on its own root: blue's run seen as {seen!r} after green started, finished {final!r}; green healthy: {green_client.get('/health').json()}")
    green.RUN_EXECUTOR.shutdown(wait=True)
