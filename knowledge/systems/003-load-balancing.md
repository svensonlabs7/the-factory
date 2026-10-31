# 3. Load Balancing

Track: J. Networking · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)upstream |least_conn|load.?balanc|round.?robin|--workers`

## What it is
A load balancer spreads incoming requests across several interchangeable backends so no one of them is overwhelmed while others sit idle, and so a dead backend is taken out of rotation. It sits behind one address (often the reverse proxy or CDN — 004-reverse-proxies.md) and picks a backend per request by some policy:
- **Round-robin:** rotate through backends in order. Simple, stateless, but blind to how busy each one is.
- **Weighted round-robin:** rotate but give bigger backends more turns.
- **Least-connections / least-load:** send each request to the backend with the fewest in-flight requests (or least queued work) — adapts to heterogeneous request costs.
- **Power of two choices (P2C):** pick two backends at random and send to the less busy of the two. Nearly as good as least-connections with O(1) state, the standard result for large fleets.
- **Hashing / consistent hashing:** route by a key (client IP, session) so the same key lands on the same backend — needed for session affinity and cache locality (030-sharding.md).

A health check removes a backend that fails, and the balancer must drain in-flight work before removing one deliberately.

## When it is worth it
- Worth it the moment you run **more than one backend** that must share traffic, or need a dead instance pulled from rotation automatically. It is the companion of horizontal scaling (046-horizontal-scaling.md): scaling out is pointless if traffic does not spread.
- The algorithm matters once request costs or backends are **heterogeneous**: round-robin is fine for uniform, cheap requests, but with a heavy tail of expensive requests it piles work on a busy backend and the tail latency blows up (proof). Then least-connections or P2C earns its keep.
- Over-engineering: a **single backend** has nothing to balance. A load balancer in front of one instance adds a hop and a failure mode and distributes nothing; what a single instance needs is admission control (shed load past capacity), not balancing.

## How it fails
- **Blind policy on skewed load:** round-robin keeps sending requests to a backend stuck on an expensive request, so they queue behind it while other backends idle → tail latency multiplies (proof: round-robin p99 ~4× least-connections at the same load).
- **Dead backend still in rotation:** no health check, or one that only pings TCP, so a backend that accepts connections but returns errors keeps getting traffic (056-health-checks.md, 057-liveness-readiness-probes.md).
- **Lost session affinity:** a stateful backend is balanced per-request with no affinity, so a user's requests hit backends that do not have their session (046-horizontal-scaling.md: keep state out of the process instead).
- **No connection draining:** a backend is removed mid-request (deploy, scale-in), killing in-flight work (054-rolling-deployments.md).
- **Thundering retry on one backend:** a backend flaps, its load shifts to the rest, pushing them over and cascading (010-circuit-breakers.md).
- **Balancer is a SPOF:** the single balancer has no redundancy, so its failure takes everything down (085-failover.md).

## Review checklist
- [ ] **Does the dispatch policy match the request-cost distribution?** · Applies when: the diff adds or changes load balancing across backends. · Block if: it uses round-robin (or a static hash) while request costs are heavy-tailed or backends are heterogeneous, so a busy backend keeps receiving work — use least-connections/least-load or P2C.
- [ ] **Are unhealthy backends removed by a meaningful health check?** · Applies when: the diff configures a pool of backends. · Block if: there is no health check, or it checks only TCP/port liveness while the backend can still return errors.
- [ ] **Is in-flight work drained before a backend leaves the pool?** · Applies when: the diff lets backends be removed (deploy, scale-in, health failure). · Block if: removal terminates in-flight requests with no drain.
- [ ] **Is load balancing justified here at all?** · Applies when: the diff introduces a load balancer. · Block if: there is a single backend and the real need is admission control / shedding, not distribution. · tripwire

## In the factory
- **The edge balances; the origin has nothing to balance.** Cloudflare's anycast routes each client to a nearby POP (responses carry `cf-ray …-EWR`, Newark — 097-dns.md), balancing clients across Cloudflare's own fleet. That is load balancing the factory gets for free and writes no code for.
- **Behind the tunnel there is exactly one origin:** a single `uvicorn` with no `--workers` (`com.svenson.factory-intake.plist:19-24`) and a single-worker executor `ThreadPoolExecutor(max_workers=1)` (`webhook_adapter.py:151`), which serialises build runs on purpose. With one backend, a load balancer would distribute nothing. Right.
- **What the factory has instead is admission control**, which the checklist explicitly distinguishes from balancing: `/trigger` returns 429 once `MAX_PENDING = 5` runs are in flight or `MAX_RUNS_PER_DAY` is reached (`webhook_adapter.py:72,220-231`). That sheds excess load; it does not spread it, because there is nowhere to spread it to.
- Not applicable at today's load: least-connections/P2C policies, backend pools, health-checked rotation, connection draining, sticky sessions. They become relevant only if the factory ever runs multiple origins (046-horizontal-scaling.md), which one operator does not need.

## Proof
`python3 knowledge/systems/proofs/003_load_balancing.py`, a discrete-event sim: 3 identical backends, Poisson arrivals at ~0.66 utilisation, service times 90% cheap (~0.5) and 10% expensive (~5.0); the same arrivals and service times fed to each policy:
```
round-robin : mean wait 6.635  p99 wait 62.079  max wait 69.774
least-conn  : mean wait 1.436  p99 wait 14.465  max wait 16.076
p2c         : mean wait 1.642  p99 wait 14.016  max wait 26.596
```
All three are stable (no exploding queue), so this isolates the tail: round-robin's p99 is ~4× least-connections because it keeps dispatching to a backend parked on an expensive request, while least-connections and P2C route around it. P2C matches least-connections while inspecting only two backends.

## Related
004-reverse-proxies.md, 046-horizontal-scaling.md, 045-autoscaling.md, 056-health-checks.md, 030-sharding.md, 085-failover.md, 001-rate-limiting.md

## Sources
- "Load Balancing in the Datacenter", Google SRE Book, ch. 20: https://sre.google/sre-book/load-balancing-datacenter/
- "HTTP Load Balancing" (round-robin, least_conn, hash), NGINX documentation: https://docs.nginx.com/nginx/admin-guide/load-balancer/http-load-balancer/
