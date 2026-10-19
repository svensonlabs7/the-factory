# 49. Edge Caching

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

## What it is
Edge caching is serving responses from a cache at the network edge (a CDN POP, a reverse proxy) under rules the origin sets per response. Beyond the basic freshness lifetime (`max-age`, or `s-maxage` for shared caches only), two directives from RFC 5861 change what happens after expiry:
- **`stale-while-revalidate=N`:** caches "MAY serve the response in which it appears after it becomes stale" for N seconds, while refreshing in the background. No client waits on the origin when an entry expires.
- **`stale-if-error=N`:** when the origin fails with 500, 502, 503 or 504, "a cached stale response MAY be used". An origin outage becomes stale-but-available.

The cache key decides who shares an entry. `Vary` names the request headers a response depends on. Cloudflare "doesn't honor Vary by default" beyond `Accept-Encoding`, so a per-language or per-device response must be keyed explicitly or not cached.

Each CDN has its own quirks. On Cloudflare, `s-maxage` implies `proxy-revalidate` and disables stale serving, and `stale-if-error` is ignored when `no-store`, `no-cache` or `must-revalidate` is present.

## When it is worth it
Edge caching rules are worth setting for public content that is read often and changes predictably: pages, API responses that are the same for everyone, assets. `stale-while-revalidate` suits content where seconds of staleness are fine and origin latency is not. `stale-if-error` suits anything whose availability matters more than freshness during an origin outage. Keep per-user, authenticated or rapidly changing responses out of edge caches entirely (048-cdn.md). Then none of these directives apply.

## How it fails
- **Expiry stalls clients:** with `max-age` only, the first request after each expiry waits for the full origin round trip, and under load many wait at once (proof A).
- **Origin outage passes straight through:** without `stale-if-error`, a 503 from the origin reaches users even though a perfectly good cached copy exists (proof B).
- **Wrong variant served:** the response varies by a header (language, device, auth) that the cache key ignores → users get someone else's variant (proof C).
- **Directive conflicts:** `s-maxage` with `stale-while-revalidate`, or `must-revalidate` with `stale-if-error`, quietly disables stale serving on some CDNs.
- **Stale forever by mistake:** a large `stale-if-error` hides a dead origin for days, and nobody notices because users still get pages.
- **Edge and browser TTL mixed up:** `max-age` meant for the edge also pins content in browsers, where it cannot be purged.

## Review checklist
- [ ] **Is the response safe to share at the edge?** · Applies when: the diff adds caching headers to a response served through a CDN or shared proxy. · Block if: the response can differ per user or per authentication state and is not marked `private` or `no-store`.
- [ ] **Does the cache key cover every input the response varies on?** · Applies when: the diff makes a response depend on a request header, cookie or query parameter and allows it to be cached. · Block if: the cache key (or a `Vary` the CDN honours) does not include that input.
- [ ] **Is behaviour at expiry and on origin failure chosen?** · Applies when: the diff sets edge cache lifetimes for content whose availability or latency matters. · Block if: there is no `stale-while-revalidate` or `stale-if-error` decision, so expiry stalls clients or an origin 5xx is passed straight through.
- [ ] **Do the directives work together on this CDN?** · Applies when: the diff combines cache directives. · Block if: a combination disables another on the target CDN (for example `s-maxage` with stale serving on Cloudflare).
- [ ] **Is stale serving bounded and visible?** · Applies when: the diff enables serving stale content. · Block if: the stale window is unbounded or long, with nothing alerting that the origin is failing.

## In the factory
- No factory response is edge-cached. Both hostnames are behind Cloudflare Access, and the dashboard data is live and per-operator (048-cdn.md). That is right, and none of these directives are needed at the edge.
- The dashboard already does the client-side equivalent of `stale-if-error`, with the staleness made visible. When a refresh fails, `factory/intake/command.html` keeps the last good figures and shows the banner "Can't reach the factory… the figures below are from the last good update" (`:105`, cleared on success at `:311-314`). It marks the factory down once `alive_at` is older than `STALE_S = 180` s (`:128`, `:194`). Right.
- The adapter's own PR cache drops data on a failed refresh instead of serving it stale (002-caching.md). That is the server-side counterpart, noted there.
- Not applicable at today's load: edge cache rules, `s-maxage`, `stale-while-revalidate` and `Vary` keys.

## Proof
`python mastery/049_edge.py` (Python 3.11, httpx). It runs a real HTTP origin answering in 300 ms, behind a small caching proxy that implements `max-age`, `stale-while-revalidate`, `stale-if-error` and `Vary`-keyed entries:
```
A  max-age=1                              first request after expiry: 200 'v2 Hello'  MISS                     314 ms
A  max-age=1, stale-while-revalidate=30   first request after expiry: 200 'v3 Hello'  STALE (revalidating)       1 ms
B  max-age=1                              origin 503 after expiry:   503 ''          MISS                     321 ms
B  max-age=1, stale-if-error=60           origin 503 after expiry:   200 'v6 Hello'  STALE (origin error)     316 ms
C  cache key ignores Vary                 German user gets:          200 'v7 Hello'  HIT                        0 ms
C  cache key includes Vary                German user gets:          200 'v9 Hallo'  MISS                     317 ms
```

## Related
048-cdn.md, 002-caching.md, 050-cache-invalidation.md, 091-latency.md, 058-monitoring.md

## Sources
- RFC 5861, "HTTP Cache-Control Extensions for Stale Content": https://www.rfc-editor.org/rfc/rfc5861.html
- "Origin Cache Control", Cloudflare Cache documentation: https://developers.cloudflare.com/cache/concepts/cache-control/
