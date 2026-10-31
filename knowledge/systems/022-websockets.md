# 22. WebSockets

Track: F. Async and messaging · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)websocket|\bwss?://|@app\.websocket`

## What it is
WebSocket (RFC 6455) upgrades an HTTP request into a persistent, two-way, message-framed TCP connection. After the opening handshake, client and server can each send messages at any time. Client frames are masked so intermediaries cannot be tricked into treating them as HTTP. Ping and Pong frames "serve either as a keepalive or as a means to verify that the remote endpoint is still responsive." Close frames end the session with a code.

The security trap is the handshake. It is an ordinary HTTP request, so browsers attach the site's cookies, but CORS does not apply to WebSockets. Any web page can open a socket to any server, and only the server's check of the `Origin` header stops a malicious page from using the victim's session. That attack is Cross-Site WebSocket Hijacking (CSWSH). RFC 6455 says the Origin header "is used to protect against unauthorized cross-origin use of a WebSocket server."

## When it is worth it
WebSockets are worth it when both sides send frequently and need low latency: chat, collaborative editing, multiplayer state, interactive terminals. For server-to-client updates only, SSE is simpler and resumes on its own (024-server-sent-events.md). For occasional updates, polling is simpler still. A WebSocket service needs:
- an async server;
- an Origin allowlist;
- authentication at the handshake and authorization per message;
- message-size and rate limits;
- heartbeats;
- reconnection with state resync in the client, since nothing resumes on its own.

## How it fails
- **Cross-Site WebSocket Hijacking:** the server authenticates the handshake by cookie and does not check `Origin` → a page on another site opens a socket as the logged-in user and reads or sends data.
- **Dead connections never noticed:** a peer vanishes without a close (sleep, network change, half-open TCP), and no ping is sent → the server holds the connection, its memory and its subscriptions forever, and the client believes it is still connected.
- **Authorization only at connect:** permissions checked once; a long-lived socket keeps acting after logout, expiry or a role change.
- **Unbounded messages:** the default size limit is large (uvicorn allows 16 MiB) → one client can push huge frames or floods.
- **No resync on reconnect:** the client reconnects but misses messages sent meanwhile (unlike SSE, there is no built-in last-event ID).
- **Idle cut by intermediaries:** proxies and CDNs close quiet sockets unless something is sent periodically.

## Review checklist
- [ ] **Is the handshake's Origin checked against an allowlist?** · Applies when: the diff adds a WebSocket endpoint that a browser can reach and that uses cookie or ambient credentials. · Block if: it accepts connections without comparing `Origin` with an explicit allowlist (CORS does not protect WebSockets).
- [ ] **Are dead connections detected?** · Applies when: the diff adds or configures a WebSocket server or client. · Block if: pings are disabled, or the ping interval plus timeout exceeds the idle timeout of any proxy on the path, so half-open sockets are never closed.
- [ ] **Is every message authorized and bounded?** · Applies when: the diff handles incoming WebSocket messages. · Block if: messages act with only the handshake's authorization, after the session may have expired, or there is no size limit below the server default and no rate limit.
- [ ] **Does the client resynchronise after a reconnect?** · Applies when: the diff adds a WebSocket client whose state depends on received messages. · Block if: a reconnect resumes without fetching current state or replaying from a known position.
- [ ] **Is two-way messaging needed?** · Applies when: the diff introduces WebSockets. · Block if: only the server sends (use SSE) or updates are infrequent (use polling).

## In the factory
- The factory has no WebSockets. The live adapter could not serve one anyway: its launch installs `fastapi` and `uvicorn` without a WebSocket library (`factory/intake/com.svenson.factory-intake.plist:9-16`). The dashboard short-polls (023-long-polling.md). That is right: one operator, updates every 15 s, and nothing the browser sends but page loads.
- The trap matters if a socket is ever added to `dash.svensonlabs.dev`. Cloudflare Access authenticates by cookie, and `/command/data` is safe from other origins today only because the same-origin policy stops them reading the response, and the adapter sends no CORS headers to relax it (076-cors.md). A WebSocket gets no such protection. It would need an Origin allowlist (`https://dash.svensonlabs.dev`), pings well under Cloudflare's 125 s timeout, and a message-size cap.
- Not applicable at today's load: WebSocket servers, heartbeat tuning and per-message authorization.

## Proof
`python harness.py` in `knowledge/systems/proofs/022/` runs `ws_app.py` under real uvicorn 0.54 (Python 3.11) with a `websockets` client. The "operator" cookie stands in for an Access session. A frozen client is a real process stopped with `SIGSTOP` while its socket stays open:
```
A  evil.example -> /ws (cookie only):          opened, read 'run 920d7293: completed, PR #56'
A  evil.example -> /ws_checked (Origin allowlist): refused: HTTP 403
B  pings off, client frozen:  open 1, closed by the server within 6 s: 0
B  pings 1 s, timeout 1 s:    open 1, closed by the server within 6 s: 1
```
uvicorn's defaults are a 20 s ping interval, a 20 s ping timeout and a 16 MiB maximum message (`uvicorn --help`).

## Related
024-server-sent-events.md, 023-long-polling.md, 076-cors.md, 077-csrf.md, 069-oauth.md, 044-backpressure.md

## Sources
- RFC 6455, "The WebSocket Protocol": https://www.rfc-editor.org/rfc/rfc6455.html
- "WebSocket Security Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html
