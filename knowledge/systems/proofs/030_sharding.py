"""Sharding, measured on 100,000 keys.
A. Resharding cost when going from 4 to 5 shards: hash(key) % N moves most keys; consistent hashing with 100 virtual
   nodes per shard (Dynamo, section 4.2) moves about 1/5.
B. Shard key choice: range sharding on a monotonically increasing key (run start time) sends every new write to the
   last shard; hashing the same key spreads them.
C. A query that lacks the shard key must ask every shard (scatter-gather)."""
import bisect
import hashlib
from collections import Counter


def h(s):
    return int(hashlib.md5(s.encode()).hexdigest(), 16)


keys = [f"run-{i}" for i in range(100_000)]


def modulo(n):
    return {k: h(k) % n for k in keys}


class Ring:
    def __init__(self, shards, vnodes=100):
        self.points = sorted((h(f"{s}#{v}"), s) for s in range(shards) for v in range(vnodes))
        self.hashes = [p for p, _ in self.points]

    def owner(self, k):
        i = bisect.bisect(self.hashes, h(k)) % len(self.points)
        return self.points[i][1]


before, after = modulo(4), modulo(5)
moved_mod = sum(before[k] != after[k] for k in keys) / len(keys)
r4, r5 = Ring(4), Ring(5)
moved_ring = sum(r4.owner(k) != r5.owner(k) for k in keys) / len(keys)
load = Counter(r5.owner(k) for k in keys)
print(f"A  4 -> 5 shards, hash % N:            {moved_mod:.0%} of keys move")
print(f"A  4 -> 5 shards, consistent hashing:  {moved_ring:.0%} of keys move (ideal 20%); per-shard load {sorted(load.values())}")

# B: the last 10,000 writes (newest start times), range-sharded on start time vs hashed.
starts = list(range(100_000))
bounds = [25_000, 50_000, 75_000]                   # 4 range shards fixed when the table was split
new = starts[-10_000:]
range_load = Counter(bisect.bisect(bounds, t) for t in new)
hash_load = Counter(h(str(t)) % 4 for t in new)
print(f"B  newest 10,000 writes, range on start time: {dict(sorted(range_load.items()))}")
print(f"B  newest 10,000 writes, hashed start time:   {dict(sorted(hash_load.items()))}")

# C: lookups with and without the shard key.
shard_of = {k: h(k) % 4 for k in keys}
targeted = 1                                          # the key names the shard
by_status = len(set(shard_of.values()))               # "all failed runs": status is not the shard key
print(f"C  get run-777 by key: {targeted} shard asked; list runs by status: {by_status} shards asked (every one)")
