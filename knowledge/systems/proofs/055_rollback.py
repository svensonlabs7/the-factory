"""Rollbacks.
A. A one-way format change: v2 writes compressed state, so rolling back to v1 breaks every read. A two-phase deploy
   (v1.5 reads both formats but still writes the old one; v2 then starts writing the new one) makes the rollback safe.
B. The real adapter as the "old" version after a rollback: restart it on run files a newer version wrote."""
import gzip
import importlib
import json
import sys
import time

from test_adapter import adapter  # noqa: F401  (fixture)


def v1_read(raw: bytes) -> dict:
    return json.loads(raw)


def v15_read(raw: bytes) -> dict:  # Prepare: understands the new format, still writes the old one
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def v2_write(state: dict) -> bytes:  # Activate: starts writing the new format
    return gzip.compress(json.dumps(state).encode())


def test_two_phase():
    raw = v2_write({"status": "queued"})
    try:
        v1_read(raw)
        one_phase = "ok"
    except Exception as exc:
        one_phase = f"{type(exc).__name__}"
    print(f"\nA  one phase: v2 wrote compressed state, roll back to v1 -> read fails: {one_phase}")
    print(f"A  two phase: v1.5 deployed first, v2 wrote compressed state, roll back to v1.5 -> {v15_read(raw)}")


def restart(module):
    sys.modules.pop("factory.intake.webhook_adapter", None)
    return importlib.import_module("factory.intake.webhook_adapter")


def test_adapter_after_rollback(adapter):
    module, root, client = adapter
    logs = module.LOG_DIR
    # A newer version added a field and a new in-flight status, and was rolled back while that run was in flight.
    (logs / "future1.meta.json").write_text(json.dumps({"run_id": "future1", "status": "fixing", "queued_at": time.time(), "round": 2}))
    old = restart(module)
    run = old._load("future1")
    old._update("future1", note="written by the old version")
    kept = "round" in old._load("future1")
    pending, _ = old._capacity(old._runs())
    print(f"B  unknown status after rollback restart: status still {run['status']!r} (not closed out), counted in flight: {pending}; unknown field kept on rewrite: {kept}")
    old.RUN_EXECUTOR.shutdown(wait=True)

    # A newer version changed the file format.
    (logs / "future2.meta.json").write_bytes(v2_write({"status": "queued"}))
    try:
        restart(old)
        started = "started"
    except Exception as exc:
        started = f"import fails: {type(exc).__name__} in _recover -> launchd KeepAlive restarts it into the same crash"
    print(f"B  one meta file in a new format, old version restarts -> {started}")
    (logs / "future2.meta.json").unlink()
    restart(old).RUN_EXECUTOR.shutdown(wait=True)
