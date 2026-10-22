"""Distributed locks and fencing tokens (Kleppmann's scenario), in simulated time.
A lock service grants 10 s leases with an increasing token. Client 1 takes the lock (token 33), then pauses for 15 s
(GC, VM freeze, network stall). Its lease expires; client 2 takes the lock (token 34) and writes. Client 1 wakes,
still believing it holds the lock, and writes too.
A. Storage that trusts the lock: both writes land, and client 1's stale write overwrites client 2's.
B. Storage that checks fencing tokens: client 1's write carries 33 < 34 and is rejected."""


class LockService:
    def __init__(self):
        self.token, self.holder, self.expires = 32, None, 0.0

    def acquire(self, client, now, lease=10.0):
        if self.holder and now < self.expires:
            return None
        self.token += 1
        self.holder, self.expires = client, now + lease
        return self.token


class Storage:
    def __init__(self, fencing):
        self.fencing, self.highest, self.value, self.log = fencing, 0, None, []

    def write(self, client, token, value):
        if self.fencing and token < self.highest:
            self.log.append(f"{client} token {token}: REJECTED (already saw {self.highest})")
            return
        self.highest = max(self.highest, token)
        self.value = value
        self.log.append(f"{client} token {token}: wrote {value!r}")


for fencing in (False, True):
    lock, store = LockService(), Storage(fencing)
    t1 = lock.acquire("client1", now=0)                 # client 1 holds the lock until t=10
    t2 = lock.acquire("client2", now=15)                # client 1 is paused; its lease has expired
    store.write("client2", t2, "client2's data")      # t=15
    store.write("client1", t1, "client1's stale data")  # t=16: client 1 wakes and writes
    label = "B  with fencing tokens   " if fencing else "A  lock only, no fencing "
    print(f"{label}: {store.log}; final value {store.value!r}")
