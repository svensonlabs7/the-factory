"""Query optimization on SQLite (stdlib), 1,000,000 runs and 3,000,000 events.
A. Deep pagination: OFFSET reads and discards every skipped row; keyset (seek) pagination jumps straight there.
B. Per-row correlated subquery vs one grouped join, for "each recent run with its event count"; plans shown.
(C, the factory's batched vs per-PR gh calls, was run separately against the real GitHub API.)"""
import random
import sqlite3
import time

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE runs(id INTEGER PRIMARY KEY, queued_at REAL, status TEXT)")
db.execute("CREATE TABLE events(run_id INTEGER, name TEXT)")
rng = random.Random(1)
db.executemany("INSERT INTO runs VALUES (?,?,?)", ((i, 1.7e9 + i, rng.choice(["completed", "failed"])) for i in range(1_000_000)))
db.executemany("INSERT INTO events VALUES (?,?)", ((rng.randrange(1_000_000), "e") for _ in range(3_000_000)))
db.execute("CREATE INDEX runs_time ON runs(queued_at, id)")
db.execute("CREATE INDEX events_run ON events(run_id)")


def timed(sql, args=()):
    t = time.perf_counter()
    rows = db.execute(sql, args).fetchall()
    return rows, (time.perf_counter() - t) * 1e3


for page in (1, 1_000, 50_000):
    off, t_off = timed("SELECT id FROM runs ORDER BY queued_at DESC, id DESC LIMIT 20 OFFSET ?", ((page - 1) * 20,))
    if page == 1:
        key, t_key = timed("SELECT id, queued_at FROM runs ORDER BY queued_at DESC, id DESC LIMIT 20")
    else:  # the last row of the previous page is the cursor
        cur = db.execute("SELECT queued_at, id FROM runs ORDER BY queued_at DESC, id DESC LIMIT 1 OFFSET ?", ((page - 1) * 20 - 1,)).fetchone()
        key, t_key = timed("SELECT id, queued_at FROM runs WHERE (queued_at, id) < (?, ?) ORDER BY queued_at DESC, id DESC LIMIT 20", cur)
    same = [r[0] for r in off] == [r[0] for r in key]
    print(f"A  page {page:>6}: OFFSET {t_off:8.2f} ms   keyset {t_key:6.2f} ms   same rows: {same}")

recent = "SELECT id FROM runs ORDER BY queued_at DESC LIMIT 2000"
corr = f"SELECT r.id, (SELECT count(*) FROM events e WHERE e.run_id = r.id) FROM ({recent}) r"
grouped = f"SELECT r.id, count(e.run_id) FROM ({recent}) r LEFT JOIN events e ON e.run_id = r.id GROUP BY r.id"
unindexed = f"SELECT r.id, (SELECT count(*) FROM events AS e NOT INDEXED WHERE e.run_id = r.id) FROM (SELECT id FROM runs ORDER BY queued_at DESC LIMIT 20) r"
for label, sql in (("correlated, indexed", corr), ("grouped join, indexed", grouped), ("correlated, NO index (20 runs)", unindexed)):
    rows, ms = timed(sql)
    plan = " | ".join(r[3] for r in db.execute("EXPLAIN QUERY PLAN " + sql))
    print(f"B  {label:<31} {ms:8.1f} ms  [{plan[:110]}]")
