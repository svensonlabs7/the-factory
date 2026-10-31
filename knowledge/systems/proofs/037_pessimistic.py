"""Pessimistic locking.
A. SQLite write lock: writer 1 takes it (BEGIN IMMEDIATE) and does 2 s of slow work while holding it. Writer 2 waits,
   and with a 0.5 s timeout gives up; nothing is lost, but the lock's hold time becomes everyone's latency.
B. The adapter's real HEARTBEAT_LOCK (fixture): how long one _set_heartbeat actually holds it.
C. The live adapter's listening port is itself an exclusive lock: a second instance on 127.0.0.1:7654 cannot bind."""
import errno
import os
import socket
import sqlite3
import tempfile
import threading
import time

from test_adapter import adapter  # noqa: F401  (fixture)


def test_sqlite_write_lock():
    path = os.path.join(tempfile.mkdtemp(), "db.sqlite")
    sqlite3.connect(path).executescript("CREATE TABLE runs(id INTEGER PRIMARY KEY, status TEXT); INSERT INTO runs VALUES (1, 'queued');")
    holding = threading.Event()

    def writer1():
        c = sqlite3.connect(path, isolation_level=None)
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE runs SET status = 'running' WHERE id = 1")
        holding.set()
        time.sleep(2)  # slow work while holding the write lock
        c.execute("COMMIT")
    t = threading.Thread(target=writer1)
    t.start()
    holding.wait()
    for timeout in (0.5, 5):
        c2 = sqlite3.connect(path, timeout=timeout, isolation_level=None)
        start = time.time()
        try:
            c2.execute("UPDATE runs SET status = 'cancelled' WHERE id = 1")
            print(f"\nA  writer 2 (timeout {timeout} s): succeeded after {time.time() - start:.1f} s, once writer 1 committed")
        except sqlite3.OperationalError as e:
            print(f"\nA  writer 2 (timeout {timeout} s): {e} after {time.time() - start:.1f} s")
    t.join()


def test_heartbeat_hold_time(adapter):
    module, root, client = adapter
    real_lock = module.HEARTBEAT_LOCK
    holds = []

    class Timed:
        def __enter__(self):
            real_lock.acquire(); self.t = time.perf_counter()

        def __exit__(self, *a):
            holds.append(time.perf_counter() - self.t); real_lock.release()
    module.HEARTBEAT_LOCK = Timed()
    for i in range(500):
        module._set_heartbeat(pipeline_status=f"tick {i}", alive_at="now")
    module.HEARTBEAT_LOCK = real_lock
    holds.sort()
    print(f"B  HEARTBEAT_LOCK hold per _set_heartbeat (500 calls): median {holds[250] * 1e3:.2f} ms, max {holds[-1] * 1e3:.2f} ms")


def test_port_is_a_lock():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 7654))
        print("C  bound 127.0.0.1:7654: no adapter is running")
    except OSError as e:
        print(f"C  second instance binding 127.0.0.1:7654: {errno.errorcode.get(e.errno, e.errno)} ({e.strerror})")
    finally:
        s.close()
