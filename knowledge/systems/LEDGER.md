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
| 38 | Distributed Locks | todo | |
| 41 | Memory Leaks | todo | |
| 42 | Garbage Collection | todo | |

## E. Delivery and change

| # | Topic | Status | Card |
|---|---|---|---|
| 6 | CI/CD | todo | |
| 55 | Rollbacks | todo | |
| 51 | Feature Flags | todo | |
| 54 | Rolling Deployments | todo | |
| 52 | Blue-Green Deployment | todo | |
| 53 | Canary Releases | todo | |
| 81 | Database Migrations | todo | |
| 82 | Schema Versioning | todo | |
| 102 | API Versioning | todo | |
| 103 | Semantic Versioning | todo | |
| 108 | Dependency Hell | todo | |
| 107 | Build Caching | todo | |

## F. Async and messaging

| # | Topic | Status | Card |
|---|---|---|---|
| 15 | Message Queues | todo | |
| 16 | Pub/Sub | todo | |
| 17 | Event-Driven Architecture | todo | |
| 21 | Cron Jobs | todo | |
| 23 | Long Polling | todo | |
| 24 | Server-Sent Events | todo | |
| 22 | WebSockets | todo | |

## G. Data

| # | Topic | Status | Card |
|---|---|---|---|
| 25 | Database Indexing | todo | |
| 26 | Query Optimization | todo | |
| 27 | N+1 Queries | todo | |
| 28 | Connection Pooling | todo | |
| 32 | Replication | todo | |
| 29 | Read Replicas | todo | |
| 31 | Partitioning | todo | |
| 30 | Sharding | todo | |

## H. Distributed systems

| # | Topic | Status | Card |
|---|---|---|---|
| 95 | Network Partitions | todo | |
| 34 | CAP Theorem | todo | |
| 35 | Eventual Consistency | todo | |
| 96 | Clock Skew | todo | |
| 33 | Leader Election | todo | |
| 18 | Distributed Transactions | todo | |
| 19 | Saga Pattern | todo | |

## I. Performance and scaling

| # | Topic | Status | Card |
|---|---|---|---|
| 91 | Latency | todo | |
| 92 | Throughput | todo | |
| 93 | P99 Latency | todo | |
| 94 | Tail Latency | todo | |
| 2 | Caching | todo | |
| 50 | Cache Invalidation | todo | |
| 47 | Vertical Scaling | todo | |
| 46 | Horizontal Scaling | todo | |
| 45 | Autoscaling | todo | |
| 48 | CDN | todo | |
| 49 | Edge Caching | todo | |
| 89 | Cold Starts | todo | |
| 90 | Serverless Limits | todo | |
| 88 | Cost Optimization | todo | |

## J. Networking and protocols

| # | Topic | Status | Card |
|---|---|---|---|
| 97 | DNS | todo | |
| 98 | TCP vs UDP | todo | |
| 99 | HTTP/2 & HTTP/3 | todo | |
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
