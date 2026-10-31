# 9. Service Discovery

Track: J. Networking · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)\b(consul|etcd|zookeeper|eureka)\b|service.?registry`

## What it is
Service discovery lets a caller find a live instance of a service by *name* instead of a hard-coded address, so instances can come and go (autoscaling, restarts, failover) without every caller being reconfigured. A **registry** holds the mapping from service name to the set of current instance addresses. Instances **register** when they start and are **deregistered** when they stop or fail; callers **resolve** the name to get the current set and pick one (often via a load balancer — 003-load-balancing.md). Two common shapes:
- **DNS-based:** instances are published as DNS records; callers just resolve the name. Kubernetes gives every Service a cluster DNS name this way, and Docker's embedded resolver maps container names to IPs on a user-defined network.
- **Registry-based:** a dedicated store (Consul, etcd, ZooKeeper, Eureka) that callers query, usually with health checks and TTL leases so dead instances are removed. Discovery can be **client-side** (the client queries the registry and chooses) or **server-side** (a load balancer or gateway does it and the client just calls one address).

The defining hard part is not registration but **deregistration**: a crashed instance must leave the registry quickly, or callers keep routing to a ghost.

## When it is worth it
- Worth it once instances are **dynamic**: they scale out/in, get new addresses on restart, or move between hosts, and callers cannot be hand-edited each time. It is the connective tissue of microservices and of any autoscaled fleet (045-autoscaling.md, 046-horizontal-scaling.md).
- The boundary: a **fixed, small topology** with stable addresses needs no registry. Static config, a hostname, or a pinned IP is simpler, has no moving parts, and cannot go stale. Standing up Consul/etcd for two services that never move is over-engineering — you add a distributed system (with its own consensus and failure modes — 033-leader-election.md, 034-cap-theorem.md) to avoid editing a config file.

## How it fails
- **Ghost instances (stale entries):** a dead instance is not deregistered, so callers keep selecting it and their calls fail until it ages out (proof). The fix is TTL leases with heartbeats, or active health checks that remove it.
- **TTL too long vs too short:** a long TTL means dead instances linger; a very short one means a brief heartbeat hiccup deregisters a healthy instance and causes churn (097-dns.md: the same TTL trade-off).
- **Registration race / thundering register:** many instances register at once, or an instance serves traffic before it is registered (or keeps serving after deregister with no drain — 054-rolling-deployments.md).
- **Stale client cache:** the caller caches a resolved set and does not refresh, so it misses new instances and keeps dead ones (002-caching.md).
- **Registry is a SPOF or splits:** the registry itself goes down or partitions, and callers cannot resolve — or resolve inconsistent views (095-network-partitions.md). It must be replicated, and callers need a sane fallback (last-known-good).
- **Health check too shallow:** a TCP/ping check keeps an instance that accepts connections but returns errors (056-health-checks.md).

## Review checklist
- [ ] **Are dead instances removed promptly?** · Applies when: the diff registers service instances in a registry or DNS. · Block if: deregistration relies only on clean shutdown, with no TTL lease/heartbeat or health check to evict a crashed instance.
- [ ] **Do callers refresh resolved addresses?** · Applies when: the diff resolves a service name and reuses the result. · Block if: the set is cached with no TTL or refresh, so new instances are missed and dead ones retained.
- [ ] **Is there a fallback when the registry is unavailable?** · Applies when: the diff makes a call path depend on a discovery registry. · Block if: a registry outage or partition leaves callers with no last-known-good set and no degraded path.
- [ ] **Is a discovery system justified for this topology?** · Applies when: the diff introduces a service registry or dynamic discovery. · Block if: the instances have stable, fixed addresses that static config or a hostname already covers — the registry adds a distributed dependency for no movement. · tripwire

## In the factory
- **Everything is statically addressed, and that is correct for one fixed host.** The adapter is `127.0.0.1:7654`, the egress proxy is pinned to `172.30.0.2`, and `run_agent.py:26` dials that IP directly (`grep` of `factory/`, `infra/`). Nothing moves, so there is nothing to discover. A registry here would be pure over-engineering.
- **The one real discovery mechanism is Docker's embedded DNS.** On the `factory-sandbox` network, the resolver at `127.0.0.11` maps the container name `factory-egress` to `172.30.0.2` (measured: `nslookup factory-egress` → `172.30.0.2`). The factory does not rely on it — `egress.sh` assigns the proxy a fixed `--ip` and the builder uses the literal address — which is the right call: a pinned IP cannot go stale, and there is exactly one instance.
- **The tunnel is a form of server-side registration:** `cloudflared` dials out and registers this origin with Cloudflare, which then routes the two hostnames to it (097-dns.md, 004-reverse-proxies.md). The factory writes no discovery code for this; the tunnel provides it.
- Not applicable at today's load: Consul/etcd/ZooKeeper, health-checked instance pools, client-side load-balancing with discovery, lease TTLs. They arrive only with a dynamic, multi-instance fleet, which one operator does not have.

## Proof
`python3 knowledge/systems/proofs/009_service_discovery.py`, a registry of 3 instances where B crashes at t=20 and stops heartbeating:
```
no-expiry  : B advertised for 40 ticks after it died at t=20; 10 client calls hit the dead instance
ttl-expiry : B advertised for  8 ticks after it died at t=20;  3 client calls hit the dead instance
(B's last heartbeat was t=15, so with TTL=12 it ages out at t=28 — 8 ticks after it died; no-expiry never removes it: 40 ticks of ghost to the end of the run)
```
Without expiry the registry advertises the dead instance for the rest of the run and clients keep failing against it; with a TTL lease the dead instance ages out a bounded time after its last heartbeat and resolution returns only live instances. Registration is easy; timely deregistration is the whole game.

## Related
097-dns.md, 003-load-balancing.md, 056-health-checks.md, 046-horizontal-scaling.md, 045-autoscaling.md, 033-leader-election.md, 095-network-partitions.md

## Sources
- "Service Discovery" (DNS for Services and Pods), Kubernetes documentation: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- "Service Discovery" (agents, health checks, TTL), HashiCorp Consul documentation: https://developer.hashicorp.com/consul/docs/concepts/service-discovery
