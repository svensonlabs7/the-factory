# 30. Sharding

Track: G. Data · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)\bshard|partition key|consistent.?hash` · tripwire

## What it is
Sharding splits a dataset across several independent databases or nodes (shards). Each shard holds the rows whose shard key maps to it, so storage and write throughput scale with the number of shards. Partitioning (031-partitioning.md) does this split within one database; sharding does it across machines.

Everything depends on the shard key. MongoDB's guidance names the criteria:
- **Cardinality:** "A cardinality of `7` means there can be no more than `7` chunks."
- **Frequency:** values that dominate become bottlenecks.
- **Monotonicity:** with an always-increasing key, "all new inserts are routed to the chunk with `maxKey` as the upper bound", so one shard takes every write.
- **Query patterns:** queries that include the key are routed to one shard. Queries without it "are broadcast to all shards" and "do not scale linearly."

Moving data when shards are added is the other cost. `hash(key) % N` remaps most keys when N changes. Consistent hashing places nodes on a ring, so that per the Dynamo paper adding or removing a node only affects its neighbours, and virtual nodes even out the load.

## When it is worth it
Sharding is worth it when one database can no longer hold the data or absorb the writes, after vertical scaling, read replicas (029-read-replicas.md), caching and partitioning are exhausted. Or when tenants must be isolated physically. It is a large, mostly one-way commitment:
- cross-shard joins and transactions become application problems;
- the shard key is very hard to change;
- operations multiply.

Choose the key from the dominant access pattern, usually a tenant or entity ID, hashed if it increases monotonically. Below that scale, sharding is over-engineering with a permanent tax.

## How it fails
- **Hot shard from a monotonic key:** range-sharding on a timestamp or auto-increment ID → every new write lands on the last shard, and adding shards does not help (proof B).
- **Resharding with modulo:** `hash % N` → going from 4 to 5 shards moves 80% of the data (proof A), and the move itself becomes an outage risk.
- **Scatter-gather everywhere:** frequent queries do not include the shard key → every query hits every shard, and latency follows the slowest one.
- **Cross-shard transactions:** an operation spanning two shards loses atomicity, unless sagas or two-phase commit are added (see the distributed-transactions cards).
- **Low-cardinality key:** keying by country or status caps the number of usable shards, and the big values become hot spots.
- **Uneven tenants:** one huge tenant fills its shard while the others idle.

## Review checklist
- [ ] **Does the shard key spread writes?** · Applies when: the diff chooses or changes a shard, partition or routing key for a distributed store. · Block if: the key increases monotonically (time, sequence) and is range-mapped, or has low cardinality or a dominant value, with no hashing or compound key.
- [ ] **Do the hot queries include the shard key?** · Applies when: the diff adds frequent queries against a sharded store. · Block if: they lack the key, so each one fans out to every shard on a request path.
- [ ] **Can shards be added without moving most data?** · Applies when: the diff implements key-to-shard mapping. · Block if: it uses `hash % N` (or any mapping that remaps most keys when N changes) with no consistent hashing or directory.
- [ ] **Does any operation span shards?** · Applies when: the diff writes to more than one shard in one logical operation. · Block if: it assumes atomicity across shards without a saga, outbox or two-phase protocol.
- [ ] **Is sharding justified?** · Applies when: the diff introduces sharding. · Block if: no measurement shows a single node (vertically scaled, with replicas, caching and partitioning) cannot hold the data or the write rate.

## In the factory
- The factory has no shards: one host, one adapter, one queue. Its state fits in a few megabytes.
- If it ever builds for several repositories with more than one adapter, the natural shard key is the target repository. Runs for one repo must serialize anyway (one `main`, merges in order), runs for different repos are independent, and a repo ID is high-cardinality and not monotonic.
- The single-instance assumptions would then become per-shard ownership: `_recover` closing every in-flight run (052-blue-green-deployment.md), and the single `RUN_EXECUTOR` (`factory/intake/webhook_adapter.py:151`). Each adapter would need to own only its repos' runs, or the blue-green failure repeats across shards.
- Not applicable at today's load: shard keys, consistent hashing and resharding.

## Proof
`python3 -I knowledge/systems/proofs/030_sharding.py` (100,000 keys, MD5 hash):
```
A  4 -> 5 shards, hash % N:            80% of keys move
A  4 -> 5 shards, consistent hashing:  20% of keys move (ideal 20%); per-shard load [18947, 19390, 19689, 20008, 21966]
B  newest 10,000 writes, range on start time: {3: 10000}
B  newest 10,000 writes, hashed start time:   {0: 2453, 1: 2515, 2: 2551, 3: 2481}
C  get run-777 by key: 1 shard asked; list runs by status: 4 shards asked (every one)
```

## Related
031-partitioning.md, 029-read-replicas.md, 032-replication.md, 052-blue-green-deployment.md, 038-distributed-locks.md, 034-cap-theorem.md

## Sources
- "Choose a Shard Key", MongoDB Manual: https://www.mongodb.com/docs/manual/core/sharding-choose-a-shard-key/
- DeCandia et al., "Dynamo: Amazon's Highly Available Key-value Store", SOSP 2007, section 4.2 (Partitioning Algorithm): https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf
