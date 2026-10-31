"""Schema versioning.
A. The factory's real change: `started_at` went from an ISO string to epoch seconds under the same name, with no
   version in the record. A reader written for v2 misreads v1; a version field plus an upcaster reads both.
B. The intake contract (/trigger, pydantic TriggerPayload) with the real adapter: what a newer or older sender gets."""
import datetime
import json
import time
from pathlib import Path

from test_adapter import adapter, sign  # noqa: F401  (fixture)

OLD = json.loads(next(Path("/Users/labs/projects/the-factory/.factory-logs/archive").glob("*.meta.json")).read_text())


def age_v2(run):  # a v2 reader: started_at is epoch seconds
    return time.time() - run["started_at"]


def upcast(run):  # a versioned reader: missing version means v1
    if run.get("schema", 1) == 1 and isinstance(run.get("started_at"), str):
        run = {**run, "schema": 2, "started_at": datetime.datetime.fromisoformat(run["started_at"]).timestamp()}
    return run


def test_unversioned_type_change():
    try:
        age_v2(OLD)
        result = "ok"
    except TypeError as exc:
        result = f"TypeError: {exc}"
    print(f"\nA  v2 reader on an archived v1 record (started_at={OLD['started_at']!r}): {result}")
    print(f"A  with a version field and an upcaster: age {age_v2(upcast(OLD)) / 86400:.1f} days")


def test_trigger_contract(adapter):
    module, root, client = adapter

    def post(payload):
        body = json.dumps(payload).encode()
        r = client.post("/trigger", content=body, headers=sign(body))
        return r.status_code, (r.json().get("detail") or r.json().get("status"))

    print(f"B  newer sender adds a field ('priority'): {post({'task': 'b1', 'priority': 'high'})}  (accepted, field silently dropped)")
    print(f"B  newer sender renames 'task' to 'prompt': {post({'prompt': 'b2'})[0]}")
    print(f"B  sender changes 'branch' to a number:    {post({'task': 'b3', 'branch': 7})[0]}")
