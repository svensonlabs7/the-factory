# Synthesis — the 20 checks that matter most to the factory

All 111 topics in [LEDGER.md](LEDGER.md) are proven. This is the distilled result: the twenty review-checklist items, drawn from the cards, most likely to catch a real defect in a factory PR. They are ordered by how much damage the failure they guard against would do to *this* system — one host, one queue, one operator, an autonomous agent writing code, a public repo, a QA gate. Each links the card that argues and proves it.

The factory's recurring lesson sits above all of them: **match the fix to one host's real load.** Most scale techniques (load balancing, multi-region, Kubernetes, Terraform, service discovery) are correctly *absent*; the cards mark them so, and the checks below are the ones that actually bite here. The live defects these surfaced are tracked in [GAPS.md](GAPS.md).

## Safety of the autonomous pipeline
1. **No secret reaches a commit.** The agent writes code into a public repo; block a change that could let a token, key or credential be committed without a pre-push scan. — [067-secrets-management.md](067-secrets-management.md) *(the pre-push gitleaks scan landed in #58)*
2. **Untrusted code holds no standing privilege.** Agent-generated code must hold no credential that can change production; the trusted component does the privileged step. — [068-iam.md](068-iam.md)
3. **The sandbox cannot reach the internet except through the allowlist.** Block any change that lets the build network egress directly, or that opens an unscoped side channel (including DNS). — [080-ssrf.md](080-ssrf.md), [097-dns.md](097-dns.md)
4. **Every trigger is validated at the boundary.** A request may not direct work at a base branch or an out-of-range target; validate before acting. — [005-api-gateways.md](005-api-gateways.md)
5. **A request authenticated is not a request authorized.** A trusted component acting on a less-trusted caller's request must verify entitlement, not just identity. — [004-reverse-proxies.md](004-reverse-proxies.md)

## Correctness under retry, replay and concurrency
6. **Retried or replayed work is idempotent.** A resent trigger or a retried run must not create duplicate work; key it. — [014-idempotency.md](014-idempotency.md)
7. **Shared mutable state has a single writer or a lock.** Check-then-act on run state from concurrent requests must not race. — [039-race-conditions.md](039-race-conditions.md), [043-thread-safety.md](043-thread-safety.md)
8. **Retries are bounded, backed off, and only on transient/idempotent failures.** No retry storm, no retrying a permanent error. — [010-circuit-breakers.md](010-circuit-breakers.md), [012-retries.md](012-retries.md)
9. **Every external call has a timeout.** A hung `git`, `gh`, Docker or agent call must not stall the queue forever. — [011-timeouts.md](011-timeouts.md)
10. **Consumption of the capped resource is bounded.** A loop or automation that spends the Claude plan must have a per-run and per-day limit. — [001-rate-limiting.md](001-rate-limiting.md), [088-cost-optimization.md](088-cost-optimization.md)

## Change safety
11. **Expensive work skips inputs that cannot benefit.** A per-change pipeline step must skip inputs it cannot help (paths, type), not run unconditionally. — [088-cost-optimization.md](088-cost-optimization.md)
12. **There is a fast mitigation separate from the fix.** A shippable change needs a rollback/flag to stop impact before root-causing. — [055-rollbacks.md](055-rollbacks.md), [109-production-incidents.md](109-production-incidents.md)
13. **A contract (JSON, schema, API) evolves by adding, never repurposing.** Add optional fields; never reuse a field's meaning/number. — [082-schema-versioning.md](082-schema-versioning.md), [100-grpc.md](100-grpc.md), [102-api-versioning.md](102-api-versioning.md)
14. **Dependencies and base images are pinned immutably.** CI and production must resolve the same versions; pin by lock/digest. — [108-dependency-hell.md](108-dependency-hell.md), [007-docker.md](007-docker.md)
15. **A cache entry is bounded and invalidated on write.** No unbounded or never-invalidated cache; TTL backstop every entry. — [002-caching.md](002-caching.md), [050-cache-invalidation.md](050-cache-invalidation.md)

## Operability
16. **Failure is detected automatically, not by luck.** A failure with real cost needs an alert on an actionable, symptom-level signal. — [109-production-incidents.md](109-production-incidents.md), [110-on-call.md](110-on-call.md)
17. **Health means "can deliver," not just "process alive."** A liveness-only check that misses a can't-ship state is insufficient. — [056-health-checks.md](056-health-checks.md), [057-liveness-readiness-probes.md](057-liveness-readiness-probes.md)
18. **Every rebuild input is recoverable off the lost machine, and runbooked.** No secret/credential may exist only on the one disk; the restore must be proven. — [083-disaster-recovery.md](083-disaster-recovery.md), [084-backups.md](084-backups.md)
19. **Measure before optimizing; the binding resource is observable.** Block a performance change with no measurement, and note what cannot be measured. — [066-observability.md](066-observability.md), [061-metrics.md](061-metrics.md)
20. **Injected-fault tests assert a steady-state hypothesis, fail closed, and stay in the scratchpad.** Resilience is verified, not assumed; the test cannot take the factory down. — [087-chaos-engineering.md](087-chaos-engineering.md)

---

Each item is a *block* condition for a PR, phrased in full on its card with the trigger that makes it apply and the exact condition to block on. The [thermo-nuclear](../../.claude/skills/thermo-nuclear-code-quality-review/SKILL.md) and `systems-review` gates are where these would be enforced; today the operator applies them by reading [GAPS.md](GAPS.md) and turning rows into tasks.
