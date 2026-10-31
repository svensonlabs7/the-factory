"""Partitioning.
A. SQLite, 1.2M events over 12 months: one table vs one table per month (manual range partitions).
   Retention: delete the oldest month with DELETE vs DROP TABLE. Query one month: whole table (no index) vs its partition.
B. The factory's rejected.jsonl is one unpartitioned append log, capped at 5 MB, read whole by _rejection_counts() on
   every dashboard poll (real module via tests/test_adapter.py's fixture). Filled to the cap with day-old entries:
   the read cost, then what the dashboard reports for a rejection that happens now."""
import json
import os
import sqlite3
import tempfile
import time

from test_adapter import adapter  # noqa: F401  (fixture)

MONTH = 30 * 86400


def test_sqlite_partitions():
    path = tempfile.mktemp()
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE events(t REAL, v TEXT)")
    for m in range(12):
        db.execute(f"CREATE TABLE events_m{m:02d}(t REAL, v TEXT)")
    rows = [(m * MONTH + i * 26, "x" * 40) for m in range(12) for i in range(100_000)]
    db.executemany("INSERT INTO events VALUES (?,?)", rows)
    for m in range(12):
        db.executemany(f"INSERT INTO events_m{m:02d} VALUES (?,?)", rows[m * 100_000:(m + 1) * 100_000])
    db.commit()

    t = time.perf_counter()
    db.execute("SELECT count(*) FROM events WHERE t >= ? AND t < ?", (5 * MONTH, 6 * MONTH)).fetchone()
    scan = (time.perf_counter() - t) * 1e3
    t = time.perf_counter()
    db.execute("SELECT count(*) FROM events_m05").fetchone()
    pruned = (time.perf_counter() - t) * 1e3
    print(f"\nA  one month's count: whole table {scan:6.1f} ms, its partition only {pruned:6.1f} ms")

    t = time.perf_counter()
    db.execute("DELETE FROM events WHERE t < ?", (MONTH,))
    db.commit()
    delete = (time.perf_counter() - t) * 1e3
    t = time.perf_counter()
    db.execute("DROP TABLE events_m00")
    db.commit()
    drop = (time.perf_counter() - t) * 1e3
    print(f"A  retention, drop the oldest month (100k rows): DELETE {delete:6.1f} ms, DROP partition {drop:6.1f} ms")
    os.unlink(path)


def test_rejection_log(adapter):
    module, root, client = adapter
    log = module.LOG_DIR / "rejected.jsonl"
    day_old = time.time() - 25 * 3600
    line = json.dumps({"time": day_old, "reason": "Invalid signature", "ip": "203.0.113.9", "path": "/trigger", "user_agent": "curl/8"}) + "\n"
    with log.open("w") as f:
        f.write(line * (module.REJECTION_LOG_MAX // len(line) + 1))
    t = time.perf_counter()
    for _ in range(5):
        counts = module._rejection_counts()
    ms = (time.perf_counter() - t) * 200
    print(f"B  rejected.jsonl at the cap ({log.stat().st_size / 1e6:.1f} MB, {sum(1 for _ in log.open()):,} lines): _rejection_counts() {ms:.0f} ms per dashboard poll")
    before = log.stat().st_size
    client.post("/trigger", content=b'{"task": "x"}', headers={"X-Hub-Signature-256": "sha256=bad", "X-Factory-Timestamp": str(int(time.time()))})
    print(f"B  a bad-signature request now: logged {log.stat().st_size > before}; dashboard last_24h {module._rejection_counts()['last_24h']}, last_hour {module._rejection_counts()['last_hour']}")
