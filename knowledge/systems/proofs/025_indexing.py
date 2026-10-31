"""Database indexing on SQLite (stdlib), then the factory's own "table scan" over run records.
A. Lookup by a column with and without an index: plan and time.
B. A composite index (status, queued_at) helps WHERE status=?, not WHERE queued_at>? alone (leftmost prefix).
C. A function on the indexed column defeats the index; an expression index fixes it.
D. Write cost: inserting 200k rows with 0 vs 4 indexes.
E. The adapter's _runs() parses every .meta.json on each /trigger and /command/data (tests/test_adapter.py's fixture)."""
import json
import random
import sqlite3
import time

from test_adapter import adapter  # noqa: F401  (fixture)

N = 1_000_000


def timed(db, sql, args=()):
    t = time.perf_counter()
    db.execute(sql, args).fetchall()
    ms = (time.perf_counter() - t) * 1e3
    plan = " | ".join(row[3] for row in db.execute("EXPLAIN QUERY PLAN " + sql, args))
    return f"{ms:7.2f} ms  [{plan}]"


def build():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE runs(id INTEGER PRIMARY KEY, run_id TEXT, status TEXT, queued_at REAL, email TEXT)")
    rng = random.Random(1)
    db.executemany("INSERT INTO runs(run_id, status, queued_at, email) VALUES (?,?,?,?)",
                   ((f"r{i:07d}", rng.choice(["completed", "failed", "queued", "blocked"]), 1.7e9 + i, f"User{i}@Example.com") for i in range(N)))
    return db


def test_sqlite_indexes():
    db = build()
    q = "SELECT * FROM runs WHERE run_id = ?"
    print(f"\nA  no index:              {timed(db, q, ('r0777777',))}")
    db.execute("CREATE INDEX runs_run_id ON runs(run_id)")
    print(f"A  index on run_id:       {timed(db, q, ('r0777777',))}")

    db.execute("CREATE INDEX runs_status_time ON runs(status, queued_at)")
    print(f"B  WHERE status=?:        {timed(db, 'SELECT count(*) FROM runs WHERE status = ? AND queued_at > ?', ('queued', 1.7e9 + 990_000))}")
    print(f"B  WHERE queued_at>? only: {timed(db, 'SELECT count(*) FROM runs WHERE queued_at > ?', (1.7e9 + 990_000,))}")

    db.execute("CREATE INDEX runs_email ON runs(email)")
    print(f"C  lower(email)=?:        {timed(db, 'SELECT * FROM runs WHERE lower(email) = ?', ('user777777@example.com',))}")
    db.execute("CREATE INDEX runs_email_lower ON runs(lower(email))")
    print(f"C  + expression index:    {timed(db, 'SELECT * FROM runs WHERE lower(email) = ?', ('user777777@example.com',))}")

    for k in (0, 4):
        w = sqlite3.connect(":memory:")
        w.execute("CREATE TABLE t(a TEXT, b TEXT, c REAL, d TEXT)")
        for i, col in enumerate(["a", "b", "c", "d"][:k]):
            w.execute(f"CREATE INDEX i{i} ON t({col})")
        rows = [(f"a{i}", f"b{i % 97}", random.random(), f"d{i}") for i in range(200_000)]
        t = time.perf_counter()
        w.executemany("INSERT INTO t VALUES (?,?,?,?)", rows)
        w.commit()
        print(f"D  200k inserts, {k} indexes: {(time.perf_counter() - t) * 1e3:6.0f} ms")


def test_factory_scan(adapter):
    module, root, client = adapter
    for n in (30, 900, 9000):
        for i in range(n):
            (module.LOG_DIR / f"s{i:05d}.meta.json").write_text(json.dumps({"run_id": f"s{i:05d}", "status": "completed", "queued_at": time.time() - i * 100, "task": "x" * 200}))
        t = time.perf_counter()
        for _ in range(10):
            module._capacity(module._runs())
        ms = (time.perf_counter() - t) * 100
        print(f"E  {n:>5} run records: _capacity(_runs()) {ms:7.2f} ms per /trigger (on the event loop)")
        for p in module.LOG_DIR.glob("s*.meta.json"):
            p.unlink()
