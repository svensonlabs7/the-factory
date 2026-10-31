"""Replication.
A. Leader/follower on two SQLite files. A shipper thread applies the leader's log to the follower 0.2 s behind.
   Async: writes are acknowledged after the leader commits; the leader dies mid-stream, the follower is promoted.
   Sync: a write is acknowledged only once the follower has applied it.
   Read-your-writes: write to the leader, read the follower at once; then wait until the follower has the write.
B. The factory: GitHub's view of a PR lags a push. The real _gate_results waits until the PR shows the pushed
   head; a naive single read gets the previous commit's checks (tests/test_adapter.py's fixture, `_run` plays gh)."""
import json
import queue
import sqlite3
import tempfile
import threading
import time

from test_adapter import adapter  # noqa: F401  (fixture)


class Pair:
    def __init__(self, lag):
        d = tempfile.mkdtemp()
        self.leader = sqlite3.connect(f"{d}/leader.db", check_same_thread=False)
        self.follower_path = f"{d}/follower.db"
        for db in (self.leader, sqlite3.connect(self.follower_path)):
            db.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY)")
            db.commit()
        self.log, self.applied, self.alive = queue.Queue(), 0, True
        self.lag = lag
        threading.Thread(target=self._ship, daemon=True).start()

    def _ship(self):
        follower = sqlite3.connect(self.follower_path)
        while True:
            lsn, sent = self.log.get()
            time.sleep(max(0, sent + self.lag - time.time()))
            if not self.alive:
                return
            follower.execute("INSERT INTO orders VALUES (?)", (lsn,))
            follower.commit()
            self.applied = lsn

    def write(self, n, sync=False):
        self.leader.execute("INSERT INTO orders VALUES (?)", (n,))
        self.leader.commit()
        self.log.put((n, time.time()))
        while sync and self.applied < n:   # wait for the follower's apply before acknowledging
            time.sleep(0.005)
        return n                           # acknowledged to the client

    def follower_has(self, n):
        return sqlite3.connect(self.follower_path).execute("SELECT 1 FROM orders WHERE id = ?", (n,)).fetchone() is not None


def test_async_sync_and_read_your_writes():
    for sync in (False, True):
        pair = Pair(lag=0.2)
        acked, t = [], time.perf_counter()
        for n in range(1, 51):
            acked.append(pair.write(n, sync=sync))
            time.sleep(0.01)
        per_write = (time.perf_counter() - t) / 50 * 1e3 - 10
        pair.alive = False                 # the leader dies; the follower is promoted
        time.sleep(0.05)
        lost = [n for n in acked if not pair.follower_has(n)]
        print(f"{chr(10) if not sync else ''}A  {'sync ' if sync else 'async'}: {len(acked)} writes acknowledged, {len(lost)} lost on failover {lost[:3]}{'...' if len(lost) > 3 else ''}; ~{per_write:.0f} ms added per write")

    pair = Pair(lag=0.2)
    n = pair.write(1)
    print(f"A  read-your-writes on the follower right after the write: {pair.follower_has(n)}")
    while pair.applied < n:                # read only once the follower has caught up to the write
        time.sleep(0.005)
    print(f"A  after waiting for the follower to reach the write:     {pair.follower_has(n)}")


def test_github_lag(adapter, monkeypatch):
    module, root, client = adapter
    head = {"sha": "old111"}
    checks = {"old111": [{"name": "tests", "bucket": "fail"}], "new222": [{"name": "tests", "bucket": "pass"}]}
    views = [0]

    def fake_run(*cmd, cwd=None):
        if cmd[1:3] == ("pr", "view"):
            views[0] += 1
            if views[0] == 3:              # GitHub's view catches up with the push on the third look
                head["sha"] = "new222"
            return head["sha"]
        return json.dumps(checks[head["sha"]])

    monkeypatch.setattr(module, "_run", fake_run)
    naive = json.loads(module._run("gh", "pr", "checks", "url", "--required", "--json", "name,bucket"))
    print(f"B  naive read right after pushing new222: {naive}  (the previous commit's checks)")
    print(f"B  _gate_results('url', 'new222'):        {module._gate_results('url', 'new222')}  after {views[0]} looks at the PR head")
