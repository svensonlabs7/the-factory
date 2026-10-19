# 5. API Gateways

Track: J. Networking · Status: proven · Updated: 2026-10-19

## What it is
An API gateway is the single entry point in front of one or more backend APIs that handles the concerns every request needs but no backend should re-implement: authentication and authorization, request validation, rate limiting and quotas, routing to the right service, and often TLS termination, response shaping, logging and metrics. It overlaps a reverse proxy (004-reverse-proxies.md) and a load balancer (003-load-balancing.md) — a gateway is a reverse proxy specialised for APIs, with policy enforcement moved to the edge. The point is *one enforcement boundary*: a rule added at the gateway covers every route behind it, and a backend cannot be reached without passing it, so backends stay thin and trust what arrives. In microservices it also hides topology (one public URL, many services) and gives clients a stable contract while services change behind it.

## When it is worth it
- Worth it when several cross-cutting concerns (auth, rate limiting, validation, routing) must hold for many routes or services: enforcing them once at the gateway beats copying them into each backend, where one omission is an open hole.
- A managed gateway (Cloudflare, API Gateway, Kong, an ingress controller) is usually the right build-vs-buy call; writing your own is justified only for policy a product does not offer.
- Over-engineering: a dedicated gateway *product* in front of a single small service whose own framework already does auth, validation and limits. A FastAPI app with dependency-injected auth and Pydantic validation already *is* a gateway for its own routes; bolting Kong in front of it adds a hop and operational weight for nothing. The pattern (one enforcement boundary) is right at any size; the heavyweight infrastructure is not.

## How it fails
- **Backend reachable without the gateway:** a service also listens on a route that skips the gateway, so its auth, limits and validation are bypassed (004-reverse-proxies.md, 080-ssrf.md).
- **Validation only at the gateway, trust blind behind it:** the gateway validates, but a second path (internal call, a new route) reaches the backend unvalidated, and the backend assumed the gateway checked.
- **Auth at the gateway, authorization forgotten:** the gateway proves *who* the caller is but not *what* they may do; a backend that trusts "the gateway let it through" skips per-resource authorization (068-iam.md defers here).
- **One gateway, one blast radius:** all traffic funnels through it, so its outage or a bad config change is a total outage, and it is a prime DDoS target (075-ddos-protection.md, 085-failover.md).
- **Inconsistent limits:** rate limits set per-route at the gateway but state kept per-instance, so scaling the gateway multiplies the real limit (001-rate-limiting.md, 046-horizontal-scaling.md).
- **Leaky errors:** the gateway passes backend stack traces or internal hostnames straight to clients.

## Review checklist
- [ ] **Is every backend route reachable only through the gateway?** · Applies when: the diff adds a backend route or service behind an API gateway. · Block if: the backend also accepts traffic that bypasses the gateway's auth, validation or limits.
- [ ] **Is request validation enforced before the backend acts?** · Applies when: the diff adds an endpoint that takes client input and performs a side effect. · Block if: input constraints that protect an invariant (allowed values, formats, sizes) are not checked at the entry boundary, so the backend trusts unvalidated input.
- [ ] **Does "authenticated" imply "authorized" incorrectly?** · Applies when: the diff adds a route behind gateway authentication. · Block if: the backend treats passing the gateway as permission to act on any resource, with no per-action authorization.
- [ ] **Is a heavyweight gateway justified for this surface?** · Applies when: the diff introduces a gateway product in front of a service. · Block if: there is one service whose framework already enforces auth, validation and limits, and the gateway adds a hop without a concern it uniquely handles.

## In the factory
The factory has a two-layer gateway, both bought not built, which is right for one service:
- **Cloudflare Access** fronts the dashboard hostnames (identity at the edge), and the **`/trigger` webhook route is its own gateway in code** (`factory/intake/webhook_adapter.py`). For its one backend action (`_run_agent`) it enforces, in order:
  - **authentication:** HMAC over `"<timestamp>.<body>"` (`_authenticate`, `_verify_signature`, `:180`+), plus a freshness window and replay store (`_replayed`) so a captured request cannot be resent;
  - **validation:** the `TriggerPayload` model (`:180-183`) constrains `branch` to `^factory/...`, enforcing the "never touch a base branch" invariant at the door (proof);
  - **admission:** `_check_capacity` returns 429 past `MAX_PENDING`/`MAX_RUNS_PER_DAY` (`:227-231`);
  - **routing:** the one validated action is dispatched to the single-worker executor (`:612`).
- The backend genuinely cannot be reached another way for the intake route: it binds `127.0.0.1`, reachable only through the tunnel, and `_run_agent` trusts the already-validated branch.
- The dashboard routes are the weaker half: they rely on Cloudflare Access but do not validate its JWT, so the gateway guarantee depends on nothing else reaching `localhost:7654` (the JWT Rotation and CORS rows in GAPS.md already record this — no new gap here).
- Not applicable at today's load: a gateway product (Kong, API Gateway), per-route policy configs, API key management, request/response transformation.

## Proof
`uv run --with pydantic python 005_api_gateway.py`, using the factory's exact `TriggerPayload` pattern:
```
A  gateway validation of `branch`:
   branch='factory/feat-x'         -> accepted -> 'factory/feat-x'
   branch='factory/a/b.c-1'        -> accepted -> 'factory/a/b.c-1'
   branch=None                     -> accepted -> None
   branch='main'                   -> 422 rejected
   branch='../main'                -> 422 rejected
   branch='/etc/x'                 -> 422 rejected
   branch='factory/x; rm -rf /'    -> 422 rejected
   branch='release'                -> 422 rejected
   branch='factory/'               -> 422 rejected
B  same backend, with and without the gateway, for a request asking to commit to main:
   through gateway : 422 rejected, backend never runs  <- invariant held
   direct to backend: backend commits to 'main'  <- base branch clobbered
```
The gateway rejects `main`, traversal, absolute, injection-shaped and empty branches at the entry boundary with 422; only well-formed factory branches reach the backend. The same backend, reached directly, would commit to `main` — the invariant lives in the gateway's validation, not in the backend.

## Related
004-reverse-proxies.md, 003-load-balancing.md, 001-rate-limiting.md, 014-idempotency.md, 075-ddos-protection.md, 069-oauth.md, 048-cdn.md

## Sources
- "What is an API gateway?", AWS: https://aws.amazon.com/what-is/api-gateway/
- "Kong Gateway — Key Concepts" (auth, rate limiting, routing plugins at the edge): https://docs.konghq.com/gateway/latest/key-concepts/
