# Systems Mastery Ledger

All 111 topics, grouped into tracks. Learn the tracks in order: the first ones matter most to the factory today.
`/systems-mastery` picks the first `todo` row and updates it. Keep each topic's original number.

Status: `todo` → `learned` (card written, proof reasoned) → `proven` (card written, experiment run).

## A. Resilience of calls

| # | Topic | Status | Card |
|---|---|---|---|
| 11 | Timeouts | proven | [011-timeouts.md](011-timeouts.md) |
| 12 | Retries | proven | [012-retries.md](012-retries.md) |
| 13 | Exponential Backoff | proven | [013-exponential-backoff.md](013-exponential-backoff.md) |
| 14 | Idempotency | proven | [014-idempotency.md](014-idempotency.md) |
| 10 | Circuit Breakers | proven | [010-circuit-breakers.md](010-circuit-breakers.md) |
| 1 | Rate Limiting | proven | [001-rate-limiting.md](001-rate-limiting.md) |
| 44 | Backpressure | proven | [044-backpressure.md](044-backpressure.md) |
| 20 | Dead Letter Queues | proven | [020-dead-letter-queues.md](020-dead-letter-queues.md) |
| 101 | Webhooks | proven | [101-webhooks.md](101-webhooks.md) |
| 56 | Health Checks | proven | [056-health-checks.md](056-health-checks.md) |
| 57 | Liveness & Readiness Probes | proven | [057-liveness-readiness-probes.md](057-liveness-readiness-probes.md) |

## B. Security

| # | Topic | Status | Card |
|---|---|---|---|
| 67 | Secrets Management | proven | [067-secrets-management.md](067-secrets-management.md) |
| 80 | SSRF | proven | [080-ssrf.md](080-ssrf.md) |
| 78 | SQL Injection | proven | [078-sql-injection.md](078-sql-injection.md) |
| 79 | XSS | proven | [079-xss.md](079-xss.md) |
| 77 | CSRF | proven | [077-csrf.md](077-csrf.md) |
| 76 | CORS | proven | [076-cors.md](076-cors.md) |
| 69 | OAuth | proven | [069-oauth.md](069-oauth.md) |
| 70 | JWT Rotation | proven | [070-jwt-rotation.md](070-jwt-rotation.md) |
| 71 | TLS | proven | [071-tls.md](071-tls.md) |
| 73 | Encryption in Transit | proven | [073-encryption-in-transit.md](073-encryption-in-transit.md) |
| 72 | Encryption at Rest | proven | [072-encryption-at-rest.md](072-encryption-at-rest.md) |
| 74 | WAF | proven | [074-waf.md](074-waf.md) |
| 75 | DDoS Protection | proven | [075-ddos-protection.md](075-ddos-protection.md) |

## C. Observability

| # | Topic | Status | Card |
|---|---|---|---|
| 59 | Logging | proven | [059-logging.md](059-logging.md) |
| 61 | Metrics | proven | [061-metrics.md](061-metrics.md) |
| 58 | Monitoring | proven | [058-monitoring.md](058-monitoring.md) |
| 62 | Alerts | proven | [062-alerts.md](062-alerts.md) |
| 64 | SLIs | proven | [064-slis.md](064-slis.md) |
| 63 | SLOs | proven | [063-slos.md](063-slos.md) |
| 65 | Error Budgets | proven | [065-error-budgets.md](065-error-budgets.md) |
| 60 | Distributed Tracing | proven | [060-distributed-tracing.md](060-distributed-tracing.md) |
| 66 | Observability | proven | [066-observability.md](066-observability.md) |

## D. Concurrency and correctness

| # | Topic | Status | Card |
|---|---|---|---|
| 39 | Race Conditions | proven | [039-race-conditions.md](039-race-conditions.md) |
| 43 | Thread Safety | proven | [043-thread-safety.md](043-thread-safety.md) |
| 40 | Deadlocks | proven | [040-deadlocks.md](040-deadlocks.md) |
| 36 | Optimistic Locking | proven | [036-optimistic-locking.md](036-optimistic-locking.md) |
| 37 | Pessimistic Locking | proven | [037-pessimistic-locking.md](037-pessimistic-locking.md) |
| 38 | Distributed Locks | proven | [038-distributed-locks.md](038-distributed-locks.md) |
| 41 | Memory Leaks | proven | [041-memory-leaks.md](041-memory-leaks.md) |
| 42 | Garbage Collection | proven | [042-garbage-collection.md](042-garbage-collection.md) |

## E. Delivery and change

| # | Topic | Status | Card |
|---|---|---|---|
| 6 | CI/CD | proven | [006-ci-cd.md](006-ci-cd.md) |
| 55 | Rollbacks | proven | [055-rollbacks.md](055-rollbacks.md) |
| 51 | Feature Flags | proven | [051-feature-flags.md](051-feature-flags.md) |
| 54 | Rolling Deployments | proven | [054-rolling-deployments.md](054-rolling-deployments.md) |
| 52 | Blue-Green Deployment | proven | [052-blue-green-deployment.md](052-blue-green-deployment.md) |
| 53 | Canary Releases | proven | [053-canary-releases.md](053-canary-releases.md) |
| 81 | Database Migrations | proven | [081-database-migrations.md](081-database-migrations.md) |
| 82 | Schema Versioning | proven | [082-schema-versioning.md](082-schema-versioning.md) |
| 102 | API Versioning | proven | [102-api-versioning.md](102-api-versioning.md) |
| 103 | Semantic Versioning | proven | [103-semantic-versioning.md](103-semantic-versioning.md) |
| 108 | Dependency Hell | proven | [108-dependency-hell.md](108-dependency-hell.md) |
| 107 | Build Caching | proven | [107-build-caching.md](107-build-caching.md) |

## F. Async and messaging

| # | Topic | Status | Card |
|---|---|---|---|
| 15 | Message Queues | proven | [015-message-queues.md](015-message-queues.md) |
| 16 | Pub/Sub | proven | [016-pub-sub.md](016-pub-sub.md) |
| 17 | Event-Driven Architecture | proven | [017-event-driven-architecture.md](017-event-driven-architecture.md) |
| 21 | Cron Jobs | proven | [021-cron-jobs.md](021-cron-jobs.md) |
| 23 | Long Polling | proven | [023-long-polling.md](023-long-polling.md) |
| 24 | Server-Sent Events | proven | [024-server-sent-events.md](024-server-sent-events.md) |
| 22 | WebSockets | proven | [022-websockets.md](022-websockets.md) |

## G. Data

| # | Topic | Status | Card |
|---|---|---|---|
| 25 | Database Indexing | proven | [025-database-indexing.md](025-database-indexing.md) |
| 26 | Query Optimization | proven | [026-query-optimization.md](026-query-optimization.md) |
| 27 | N+1 Queries | proven | [027-n-plus-one-queries.md](027-n-plus-one-queries.md) |
| 28 | Connection Pooling | proven | [028-connection-pooling.md](028-connection-pooling.md) |
| 32 | Replication | proven | [032-replication.md](032-replication.md) |
| 29 | Read Replicas | proven | [029-read-replicas.md](029-read-replicas.md) |
| 31 | Partitioning | proven | [031-partitioning.md](031-partitioning.md) |
| 30 | Sharding | proven | [030-sharding.md](030-sharding.md) |

## H. Distributed systems

| # | Topic | Status | Card |
|---|---|---|---|
| 95 | Network Partitions | proven | [095-network-partitions.md](095-network-partitions.md) |
| 34 | CAP Theorem | proven | [034-cap-theorem.md](034-cap-theorem.md) |
| 35 | Eventual Consistency | proven | [035-eventual-consistency.md](035-eventual-consistency.md) |
| 96 | Clock Skew | proven | [096-clock-skew.md](096-clock-skew.md) |
| 33 | Leader Election | proven | [033-leader-election.md](033-leader-election.md) |
| 18 | Distributed Transactions | proven | [018-distributed-transactions.md](018-distributed-transactions.md) |
| 19 | Saga Pattern | proven | [019-saga-pattern.md](019-saga-pattern.md) |

## I. Performance and scaling

| # | Topic | Status | Card |
|---|---|---|---|
| 91 | Latency | proven | [091-latency.md](091-latency.md) |
| 92 | Throughput | proven | [092-throughput.md](092-throughput.md) |
| 93 | P99 Latency | proven | [093-p99-latency.md](093-p99-latency.md) |
| 94 | Tail Latency | proven | [094-tail-latency.md](094-tail-latency.md) |
| 2 | Caching | proven | [002-caching.md](002-caching.md) |
| 50 | Cache Invalidation | proven | [050-cache-invalidation.md](050-cache-invalidation.md) |
| 47 | Vertical Scaling | proven | [047-vertical-scaling.md](047-vertical-scaling.md) |
| 46 | Horizontal Scaling | proven | [046-horizontal-scaling.md](046-horizontal-scaling.md) |
| 45 | Autoscaling | proven | [045-autoscaling.md](045-autoscaling.md) |
| 48 | CDN | proven | [048-cdn.md](048-cdn.md) |
| 49 | Edge Caching | proven | [049-edge-caching.md](049-edge-caching.md) |
| 89 | Cold Starts | proven | [089-cold-starts.md](089-cold-starts.md) |
| 90 | Serverless Limits | proven | [090-serverless-limits.md](090-serverless-limits.md) |
| 88 | Cost Optimization | proven | [088-cost-optimization.md](088-cost-optimization.md) |

## J. Networking and protocols

| # | Topic | Status | Card |
|---|---|---|---|
| 97 | DNS | proven | [097-dns.md](097-dns.md) |
| 98 | TCP vs UDP | proven | [098-tcp-vs-udp.md](098-tcp-vs-udp.md) |
| 99 | HTTP/2 & HTTP/3 | proven | [099-http2-http3.md](099-http2-http3.md) |
| 4 | Reverse Proxies | todo | |
| 3 | Load Balancing | todo | |
| 5 | API Gateways | todo | |
| 9 | Service Discovery | todo | |
| 100 | gRPC | todo | |

## K. Infrastructure

| # | Topic | Status | Card |
|---|---|---|---|
| 7 | Docker | todo | |
| 104 | Infrastructure as Code | todo | |
| 105 | Terraform | todo | |
| 8 | Kubernetes | todo | |
| 106 | Helm Charts | todo | |

## L. Operations and recovery

| # | Topic | Status | Card |
|---|---|---|---|
| 109 | Production Incidents | todo | |
| 110 | On-Call | todo | |
| 111 | Postmortems | todo | |
| 84 | Backups | todo | |
| 83 | Disaster Recovery | todo | |
| 85 | Failover | todo | |
| 86 | Multi-Region Deployment | todo | |
| 87 | Chaos Engineering | todo | |

## Deferred

Revisit later. These rows are picked only after every row above is done.

- **68. IAM:** paused on 2026-10-18 at the operator's request; revisit later. The audit of the factory's GitHub push identity and `main`'s protection was done, but the card was not written. When revisiting, write the card around the defensive fixes (narrowest token for the adapter, one identity per workload).

| # | Topic | Status | Card |
|---|---|---|---|
| 68 | IAM | todo | |
