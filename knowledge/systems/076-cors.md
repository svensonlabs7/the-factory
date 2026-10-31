# 76. CORS

Track: B. Security · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)\bcors\b|access-control-allow|allow_origins|trustedhost|--host\b`

## What it is
Browsers stop a page's scripts from reading responses from other origins (scheme, host and port): the same-origin policy. Cross-origin resource sharing (CORS) is how a server *relaxes* that rule. By sending `Access-Control-Allow-Origin`, the server tells the browser which other origins may read its responses. CORS adds no protection: a server with no CORS headers is the safe default.

Three facts drive every CORS bug:
- **Simple requests are still sent:** a cross-origin GET, or a form-style POST, reaches the server. The browser only hides the response.
- **Credentials need an explicit origin:** reading credentialed responses needs `Access-Control-Allow-Credentials: true` and a named origin, never `*`.
- **Browsers only:** CORS governs only browsers, so server-to-server calls ignore it entirely.

## When it is worth it
Only when a browser page on one origin must call an API on another, such as a separate frontend domain or a public browser API. Then allow an exact list of origins, add credentials only if the API is cookie-authenticated, and never reflect the incoming `Origin`. Server-to-server integrations (webhooks, bots, CLIs) need no CORS. Neither does a page that calls its own origin. Adding it "to make it work" is how internal data leaks.

## How it fails
- **Reflected origin with credentials:** the server copies the request's `Origin` into `Access-Control-Allow-Origin` and allows credentials → any website can read a logged-in user's data.
- **Wildcard on an internal or localhost service:** `Access-Control-Allow-Origin: *` on a service reachable only from the user's machine → any site the user visits reads it through their browser.
- **Loose origin matching:** a suffix, prefix or regex check accepts `trusted.com.evil.net` or `eviltrusted.com`.
- **`null` allowed:** sandboxed iframes and `file:` pages send `Origin: null`, which an attacker can produce at will.
- **Thinking CORS blocks the request:** simple GETs and POSTs still execute on the server → a side effect on GET happens even though the attacker cannot read the reply.
- **No Host check on a localhost service:** with DNS rebinding, an attacker's domain re-resolves to `127.0.0.1`, so its page becomes same-origin with the local service, and CORS no longer applies.

## Review checklist
- [ ] **Is new CORS justified by a browser caller on another origin?** · Applies when: the diff adds CORS headers or middleware. · Block if: the callers are servers, bots or the page's own origin, or no cross-origin browser client is named.
- [ ] **Is the allow-list exact?** · Applies when: the diff configures allowed origins. · Block if: it reflects the request's `Origin`, uses `*` together with credentials, allows `null`, or matches origins by prefix, suffix or unanchored regex.
- [ ] **Does a localhost or internal service stay unreadable from other sites?** · Applies when: the diff serves data from a service bound to localhost or a private network. · Block if: it sends permissive CORS, or accepts any `Host` header so that DNS rebinding can make another site same-origin with it.
- [ ] **Do cross-origin-reachable routes avoid side effects on simple requests?** · Applies when: the diff adds a GET, or a form-encoded POST, that a browser on another site could send. · Block if: the route changes state without an auth header that would force a preflight (see 077-csrf.md).

## In the factory
- `factory/intake/webhook_adapter.py`: no CORS middleware or headers anywhere. Grok Bot is server-to-server and the dashboard calls its own origin, so none is needed. Right: in a real browser, a page on another site could not read `localhost:7654/heartbeat`.
- `factory/intake/webhook_adapter.py:588-618`: the one state-changing route needs custom HMAC headers, which force a preflight that is never approved. Right (see 077-csrf.md).
- Fixed in #60 (was a low gap): the adapter answered `200` to `Host: rebind.attacker.example`, so a DNS-rebinding page visited by the operator could read `/command/data`, `/heartbeat` and `/status`. `TrustedHostMiddleware` now serves only the tunnel hostnames and localhost (`ALLOWED_HOSTS`, kept in step with `config.yml` by a test). Verified live: a foreign Host gets `400`, `dash.svensonlabs.dev` gets `200`.
- Not applicable at today's load: per-origin CORS policy. No browser client lives on another origin.

## Proof
An attacker page at `http://127.0.0.1:8801/probe` in the browser pane, reading from the live adapter and from a deliberately misconfigured service on `localhost:8803`:
```
factory adapter /heartbeat, no CORS: blocked (Failed to fetch)
service reflecting Origin + credentials: READ {"internal": "run tasks, PR links, heartbeat"}
service sending ACAO *: READ {"internal": "run tasks, PR links, heartbeat"}
```
The adapter's access log counted `GET /heartbeat` lines going from 7 to 8 across one page load: the blocked request was still sent and answered with 200, and only the read was refused. `curl -H "Host: rebind.attacker.example" localhost:7654/heartbeat` returned `200`. Whether this browser's private-network protections would also stop a rebinding page was not tested.

## Related
077-csrf.md, 079-xss.md, 080-ssrf.md, 097-dns.md, 101-webhooks.md, 070-jwt-rotation.md, 022-websockets.md

## Sources
- "Cross-Origin Resource Sharing (CORS)", MDN: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS
- "Cross-origin resource sharing (CORS)", PortSwigger Web Security Academy: https://portswigger.net/web-security/cors
