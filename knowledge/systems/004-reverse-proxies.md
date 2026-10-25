# 4. Reverse Proxies

Track: J. Networking · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)x-forwarded|x-real-ip|cf-connecting-ip|request\.client|proxy_pass|service: http`

## What it is
A reverse proxy sits in front of one or more backend servers and takes client requests on their behalf: the client connects to the proxy, the proxy forwards to a backend, and relays the response back. (A *forward* proxy is the mirror image — it sits in front of clients and reaches out to arbitrary servers; the sandbox's `tinyproxy` is one.) A reverse proxy is the single front door, and that position lets it do work the backends should not each reimplement: TLS termination, routing by host/path, load balancing (003-load-balancing.md), caching (048-cdn.md), compression, rate limiting (001-rate-limiting.md), auth, and hiding the backend topology. Because it terminates the client's TCP connection, the backend's socket peer is the *proxy*, not the client — so the proxy must pass the real client identity on in headers (`X-Forwarded-For`, `X-Forwarded-Proto`, `Host`, or a vendor header like Cloudflare's `CF-Connecting-IP`), and the backend must trust those only from a known proxy.

## When it is worth it
- Worth it as soon as something must be true for *every* backend or route: one TLS cert and cipher policy, one place to rate-limit or authenticate, one public entry point while backends stay private. Nearly every production web system has one, often the CDN itself.
- The boundary: a single backend reachable only over loopback or a private link, with nothing cross-cutting to enforce, does not need a second proxy in front of it. Adding nginx in front of one local process "for good practice" is an extra hop, extra config and an extra failure mode for no gain.

## How it fails
- **Trusting a client-supplied forwarded header:** the app reads `X-Forwarded-For` (or `CF-Connecting-IP`) as the client IP, but a request that did not pass the real proxy — or a proxy that forwards the client's own header untouched — lets the client set any IP, bypassing IP allowlists/rate limits or poisoning logs (proof).
- **Buffering / partial relay:** the proxy forwards a response before the upstream has finished, or cuts it off, so the client gets a truncated body (the factory's egress proxy hit exactly this; fixed by reading until the upstream closes — 066-observability.md era).
- **Timeout and retry mismatch:** proxy and backend disagree on timeouts, so the proxy retries or 504s a request the backend is still processing, duplicating non-idempotent work (011-timeouts.md, 014-idempotency.md).
- **Header/host confusion:** the proxy passes an attacker-controlled `Host` or forwarded header that the backend uses to build URLs or cache keys (web-cache poisoning, open redirect — 048-cdn.md).
- **Origin reachable directly:** the backend also accepts traffic that skips the proxy, so the proxy's TLS, auth and WAF are bypassed (080-ssrf.md).
- **Single point of failure:** the one front door goes down and everything behind it is unreachable, if it has no redundancy (085-failover.md).

## Review checklist
- [ ] **Is a forwarded client identity trusted only from a known proxy?** · Applies when: the diff reads `X-Forwarded-For`, `X-Real-IP`, `CF-Connecting-IP` or similar for an access decision, rate limit, or audit log. · Block if: the value is trusted without confirming the request actually came through the trusted proxy (by network path, a validated proxy token/JWT, or the rightmost trusted hop), so a client or non-proxy caller can forge it.
- [ ] **Can the backend be reached without going through the proxy?** · Applies when: the diff exposes a backend that a reverse proxy is supposed to front. · Block if: the backend also accepts direct traffic that skips the proxy's TLS, auth or WAF.
- [ ] **Do proxy and backend agree on timeouts and retries?** · Applies when: the diff sets a timeout or retry on either hop for non-idempotent work. · Block if: the proxy can time out and retry a request the backend is still running, with no idempotency key.
- [ ] **Is an added reverse proxy justified?** · Applies when: the diff puts a new proxy in front of a backend. · Block if: there is one backend on a private/loopback link and nothing cross-cutting (TLS, auth, rate limit, routing) for the proxy to enforce.

## In the factory
- **Cloudflare + `cloudflared` are the reverse proxy**, and the factory owns no proxy code. Clients reach `factory`/`dash` only through the Cloudflare edge → the tunnel → `uvicorn` on `127.0.0.1:7654` (`infra/cloudflare-tunnel/config.yml`). The edge does TLS, Access auth, routing by exact path, and HTTP/2-3 (099). The origin binds loopback, so it cannot be reached directly (the SSRF-style "origin reachable directly" failure is closed by binding, and the tunnel is outbound-only). Right.
- **The one forwarded-header trust point** is `webhook_adapter.py:564`: the rejection log records `request.headers.get("CF-Connecting-IP") or request.client.host`. For a request that truly came through Cloudflare this is the real client IP; but the adapter does not verify the hop (the JWT Rotation gap), so a request reaching `localhost:7654` another way (a local process, or the DNS-rebinding path in the CORS gap) can set `CF-Connecting-IP` to any value. It feeds only the log's `ip` field, not any access decision or the burst count, so the blast radius is a poisoned audit field. Added to GAPS.md (low).
- The factory also runs a **forward proxy** — `tinyproxy` in the sandbox egress (`factory/build/egress/tinyproxy.conf`), the opposite role: it fronts the sandbox's outbound calls and allowlists destinations (097-dns.md). Useful contrast: reverse = in front of your servers; forward = in front of your clients.
- Not applicable at today's load: a second proxy in front of the single adapter, upstream load balancing, proxy-level caching.

## Proof
`python3 knowledge/systems/proofs/004_reverse_proxy.py`, real `http.server` backend + proxy on loopback. The backend allows a request only if the leftmost `X-Forwarded-For` is an internal IP; the client sends a spoofed `X-Forwarded-For: 10.0.0.9`:
```
naive proxy (forwards client XFF): HTTP 200: ALLOW client_ip='10.0.0.9'
correct proxy (overwrites XFF)   : HTTP 403: DENY client_ip='127.0.0.1'
```
The naive proxy forwards the client's own header, so the spoof is accepted as an internal IP. The correct proxy overwrites `X-Forwarded-For` with the real TCP peer, so the backend sees the true address and denies it. The factory's edge protocols and the `CF-Connecting-IP` line are from live inspection.

## Related
003-load-balancing.md, 005-api-gateways.md, 048-cdn.md, 071-tls.md, 080-ssrf.md, 099-http2-http3.md, 001-rate-limiting.md

## Sources
- "NGINX Reverse Proxy", NGINX documentation: https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/
- "Restoring original visitor IPs" (CF-Connecting-IP / X-Forwarded-For), Cloudflare documentation: https://developers.cloudflare.com/support/troubleshooting/restoring-visitor-ips/restoring-original-visitor-ips/
