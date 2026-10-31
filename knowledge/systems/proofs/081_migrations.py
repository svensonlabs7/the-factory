"""Database migrations, on SQLite (stdlib) plus the factory's own file-format change.
A. A breaking migration (RENAME COLUMN) while the old code still runs, then the same change as expand/backfill/contract.
B. A backfill in one long transaction locks out the app's writes; the same backfill in small batches does not.
C. The factory: real old-format run records (.factory-logs/archive) put back next to current ones, read by the real
   adapter (tests/test_adapter.py's fixture)."""
import shutil
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

from test_adapter import adapter  # noqa: F401  (fixture)

ARCHIVE = Path("/Users/labs/projects/the-factory/.factory-logs/archive")


def old_app(db):   # the version still deployed: knows only `task`
    db.execute("INSERT INTO runs(task) VALUES ('old write')")
    return db.execute("SELECT task FROM runs ORDER BY id DESC LIMIT 1").fetchone()[0]


def test_breaking_vs_expand_contract():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE runs(id INTEGER PRIMARY KEY, task TEXT)")
    db.execute("ALTER TABLE runs RENAME COLUMN task TO prompt")
    try:
        old_app(db)
        result = "ok"
    except sqlite3.OperationalError as exc:
        result = f"OperationalError: {exc}"
    print(f"\nA  rename in one step, old code still running: {result}")

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE runs(id INTEGER PRIMARY KEY, task TEXT)")
    db.executemany("INSERT INTO runs(task) VALUES (?)", [(f"t{i}",) for i in range(3)])
    steps = []
    db.execute("ALTER TABLE runs ADD COLUMN prompt TEXT")                         # expand
    steps.append(("expand", old_app(db)))
    db.execute("INSERT INTO runs(task, prompt) VALUES ('new write', 'new write')")  # new code dual-writes
    db.execute("UPDATE runs SET prompt = task WHERE prompt IS NULL")              # backfill
    steps.append(("backfill", old_app(db)))
    missing = db.execute("SELECT count(*) FROM runs WHERE prompt IS NULL").fetchone()[0]
    print(f"A  expand/contract: old code after each step -> {steps}; rows still without `prompt`: {missing} (the old version's write after the backfill)")
    db.execute("UPDATE runs SET prompt = task WHERE prompt IS NULL")              # final backfill once no old version writes
    print(f"A  after the last old instance stops, a final backfill: rows without `prompt`: {db.execute('SELECT count(*) FROM runs WHERE prompt IS NULL').fetchone()[0]}")
    print("A  contract (DROP COLUMN task) waits until no deployed version reads `task`")


def test_backfill_locks(tmp_path):
    path = tmp_path / "app.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE runs(id INTEGER PRIMARY KEY, task TEXT, prompt TEXT)")
    db.executemany("INSERT INTO runs(task) VALUES (?)", [(f"t{i}",) for i in range(200_000)])
    db.commit()

    def app_writes(result):
        conn = sqlite3.connect(path, timeout=0.2)  # a request's write waits at most 200 ms for the lock
        ok = failed = 0
        end = time.time() + 1.5
        while time.time() < end:
            try:
                conn.execute("INSERT INTO runs(task) VALUES ('request')")
                conn.commit()
                ok += 1
            except sqlite3.OperationalError:
                failed += 1
            time.sleep(0.01)
        result.extend([ok, failed])

    for mode in ("one transaction", "batches of 5,000"):
        db.execute("UPDATE runs SET prompt = NULL")
        db.commit()
        result = []
        t = threading.Thread(target=app_writes, args=(result,))
        t.start()
        time.sleep(0.1)
        started = time.time()
        if mode == "one transaction":
            db.execute("UPDATE runs SET prompt = upper(task)")
            time.sleep(1.0)   # the rest of a long migration script inside the same transaction
            db.commit()
        else:
            while db.execute("UPDATE runs SET prompt = upper(task) WHERE id IN (SELECT id FROM runs WHERE prompt IS NULL LIMIT 5000)").rowcount:
                db.commit()
                time.sleep(0.02)
        took = time.time() - started
        t.join()
        print(f"B  backfill in {mode}: {took:.1f} s; app writes ok {result[0]}, failed 'database is locked' {result[1]}")


def test_factory_old_format(adapter):
    module, root, client = adapter
    for meta in ARCHIVE.glob("*.meta.json"):
        shutil.copy(meta, module.LOG_DIR / meta.name)
    status = client.get("/command/data").status_code
    one = client.get("/status/factory-20261010-174244-aa53c6")
    print(f"C  4 archived old-format runs back in LOG_DIR: /command/data -> {status}; /status -> {one.status_code} {one.json().get('status')!r}; "
          f"started_at types: {sorted({type(module._load(m.name.removesuffix('.meta.json')).get('started_at')).__name__ for m in ARCHIVE.glob('*.meta.json')})}")


def test_heartbeat_new_row(adapter, caplog):
    module, root, client = adapter
    # A later version adds a row to HEARTBEAT.template.md and sets it; the existing HEARTBEAT.md was copied earlier.
    (root / "HEARTBEAT.template.md").write_text((root / "HEARTBEAT.md").read_text() + "| **gate_minutes** | — |\n")
    module._set_heartbeat(gate_minutes="61")
    print(f"D  new template row set on an existing HEARTBEAT.md: in /heartbeat {'gate_minutes' in client.get('/heartbeat').json()}; warnings: {[r.getMessage() for r in caplog.records if 'no gate_minutes' in r.getMessage()]}")
