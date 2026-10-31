"""Cache invalidation: the stale set race, reproduced with real threads and explicit interleaving (Events).
A reader misses, reads the database (old value), and is delayed before it fills the cache. Meanwhile a writer
updates the database and invalidates the cache. Then the reader's fill lands.
A. Update-then-set-cache vs update-then-delete-cache: both can end stale.
B. Leases (Facebook's memcache): a miss returns a lease token; a delete voids outstanding leases; a fill with a void
   token is rejected, so the stale value never lands.
C. The factory: the real `_pr` (tests/test_adapter.py's fixture) after the adapter itself pushes a fix: nothing
   invalidates the entry, so the dashboard shows the pre-push checks for up to the TTL."""
import itertools
import json
import threading
import time

from test_adapter import adapter  # noqa: F401  (fixture)


class Cache:
    def __init__(self, leases):
        self.data, self.leases, self.leases_on, self.tokens = {}, {}, leases, itertools.count(1)

    def get(self, k):
        if k in self.data:
            return self.data[k], None
        token = next(self.tokens)
        self.leases[k] = token
        return None, token

    def set(self, k, v, token=None):
        if self.leases_on and self.leases.get(k) != token:
            return False                      # the lease was voided by a delete: reject the stale fill
        self.data[k] = v
        return True

    def delete(self, k):
        self.data.pop(k, None)
        self.leases.pop(k, None)


def scenario(write_mode, leases=False):
    db, cache = {"price": 10}, Cache(leases)
    read_db, writer_done = threading.Event(), threading.Event()

    def reader():
        _, token = cache.get("price")
        value = db["price"]                   # reads the OLD value (10)
        read_db.set()
        writer_done.wait()                    # the reader is slow (GC pause, network)
        cache.set("price", value, token)

    def writer():
        read_db.wait()
        db["price"] = 12
        if write_mode == "set":
            cache.set("price", 12, cache.leases.get("price") if leases else None)
        else:
            cache.delete("price")
        writer_done.set()

    threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    cached = cache.data.get("price")
    return f"db {db['price']}, cache {cached} -> {'STALE until TTL' if cached not in (None, db['price']) else 'consistent'}"


def test_races():
    print(f"\nA  update db, then set cache:    {scenario('set')}")
    print(f"A  update db, then delete cache: {scenario('delete')}")
    print(f"B  delete + leases:              {scenario('delete', leases=True)}")


def test_factory_pr_cache(adapter, monkeypatch):
    module, root, client = adapter
    url, state = "https://github.com/o/r/pull/5", {"checks": "fail"}
    monkeypatch.setattr(module, "_run", lambda *cmd, cwd=None: json.dumps(
        {"state": "OPEN", "statusCheckRollup": [{"name": "tests", "conclusion": "FAILURE" if state["checks"] == "fail" else "SUCCESS"}]}))
    module._pr_cache.clear()
    before = module._pr(url)["checks"][0]["result"]
    state["checks"] = "pass"                  # the adapter pushes a fix; the new head passes
    after = module._pr(url)["checks"][0]["result"]
    print(f"C  dashboard before the push: tests {before}; right after the push (within the 60 s TTL): tests {after}")
