# 99. HTTP/2 & HTTP/3

Track: J. Networking · Status: proven · Updated: 2026-10-19

## What it is
HTTP/1.1 sends one request/response at a time per TCP connection, so a slow response blocks the connection and browsers open ~6 connections per host to get parallelism. **HTTP/2** (RFC 9113) fixes this by multiplexing: many independent *streams* share one TCP connection, each request/response carried as interleaved frames, plus header compression (HPACK) and server push. That removes HTTP/1.1's request-level head-of-line blocking — but all streams still ride one TCP byte stream, so one lost TCP segment stalls every stream behind it until the retransmit arrives (TCP-level HOL blocking). **HTTP/3** (RFC 9114) keeps HTTP/2's stream model but runs it over **QUIC** (RFC 9000), a reliable transport built on UDP with independent per-stream delivery and its own TLS 1.3 and loss recovery. A packet loss on one QUIC stream delays only that stream, not the others, and QUIC folds the transport and TLS handshake together for a faster connection setup. Clients discover HTTP/3 from an `Alt-Svc: h3` advertisement and switch on later visits.

## When it is worth it
- You rarely implement these; you adopt them at the edge/server and let clients negotiate (ALPN for h2, `Alt-Svc` for h3). Turn them on when you serve many assets or concurrent requests per client over one connection — HTTP/2 multiplexing and header compression are a clear win there.
- **HTTP/3** earns its keep on lossy or high-latency links (mobile, long-haul): independent streams and a 1-RTT (or 0-RTT) handshake cut tail latency where TCP HOL blocking and handshake cost hurt most.
- Over-engineering: forcing h2/h3 for a single-client, low-concurrency, LAN or loopback service. On a near-lossless local link, HTTP/1.1 keep-alive is fine, TCP HOL blocking never triggers, and the multiplexing buys nothing. Running your own QUIC stack when a CDN or library already offers it is also wasted effort.

## How it fails
- **TCP HOL blocking under HTTP/2:** one dropped segment on a lossy link stalls every multiplexed stream on that connection until it is retransmitted, so one slow object delays unrelated ones (proof).
- **Too many streams or huge headers:** unbounded concurrent streams or large header sets exhaust server memory; HPACK/QPACK dynamic-table and `SETTINGS_MAX_CONCURRENT_STREAMS` limits exist for this, and ignoring them is a DoS vector (075-ddos-protection.md).
- **Assuming h3 is reachable:** UDP/443 is blocked or rate-limited on some networks, so HTTP/3 silently fails and clients must fall back to h2/TCP; a deployment that assumes h3 always works breaks there.
- **Protocol downgrade surprises:** a proxy or origin that only speaks HTTP/1.1 behind an h2/h3 edge means the edge-to-origin hop loses multiplexing; a header or body that the newer version allowed can break on the old hop.
- **Server push misused:** pushing assets the client already cached wastes bandwidth; push is deprecated in practice.
- **0-RTT replay:** QUIC/TLS 1.3 early data can be replayed, so it must carry only idempotent requests (014-idempotency.md).

## Review checklist
- [ ] **Does an edge/origin protocol mismatch lose a guarantee?** · Applies when: the diff puts an h2/h3 edge or proxy in front of an origin that speaks an older HTTP version. · Block if: the change relies on multiplexing, trailers, or header behaviour end-to-end that the origin hop (often HTTP/1.1) does not provide.
- [ ] **Are concurrent streams and header sizes bounded?** · Applies when: the diff configures or implements an HTTP/2/3 server endpoint. · Block if: there is no limit on concurrent streams or header-list size, so a client can exhaust memory.
- [ ] **Is there a fallback when HTTP/3 is unreachable?** · Applies when: the diff depends on HTTP/3. · Block if: there is no h2/TCP fallback for networks that block or throttle UDP/443.
- [ ] **Is early data (0-RTT) limited to idempotent requests?** · Applies when: the diff enables QUIC/TLS 0-RTT or h2 early data. · Block if: non-idempotent requests can be sent as early data, which can be replayed.
- [ ] **Is h2/h3 justified for this traffic?** · Applies when: the diff enables HTTP/2 or HTTP/3 for a service. · Block if: the traffic is single-client, low-concurrency and on a near-lossless link, where HTTP/1.1 keep-alive suffices and the extra machinery buys nothing.

## In the factory
- **Client ↔ edge is already HTTP/2, with HTTP/3 offered, for free.** Cloudflare terminates both public hostnames: `curl -sI --http2 https://factory.svensonlabs.dev` returns `HTTP/2 401` and `curl … https://dash.svensonlabs.dev` returns `HTTP/2 302`, and both carry `alt-svc: h3=":443"; ma=86400` (measured) — so any h3-capable client upgrades. The factory wrote no code for this; the CDN provides it (048-cdn.md).
- **Edge ↔ origin is HTTP/1.1 and that is correct.** The `cloudflared` tunnel speaks HTTP/1.1 to `uvicorn` on `127.0.0.1:7654` (`infra/cloudflare-tunnel/config.yml`). That hop is a single process over loopback, near-lossless, one operator: TCP HOL blocking never triggers and multiplexing would buy nothing. Forcing h2/h3 there would be over-engineering.
- The protocol-mismatch risk in the checklist is present but benign here: nothing the dashboard or webhook does relies on end-to-end multiplexing or trailers, so the h2-edge / h1.1-origin split loses no guarantee the factory uses.
- Not applicable at today's load: tuning stream concurrency, HPACK/QPACK tables, server push, HTTP/3 fallback logic, or running our own QUIC.

## Proof
`python3 knowledge/systems/proofs/099_http23.py`, a deterministic model of 3 streams × 4 segments multiplexed on one connection, with one segment lost and retransmitted 10 ticks later:
```
lost segment: wire index 3 = stream 0 seq 1; retransmit +10 ticks
  stream 0: HTTP/2 done at t=14   HTTP/3 done at t=14
  stream 1: HTTP/2 done at t=14   HTTP/3 done at t=11  <- stalled by stream 0's loss
  stream 2: HTTP/2 done at t=14   HTTP/3 done at t=12  <- stalled by stream 0's loss
mean completion: HTTP/2 t=14.00, HTTP/3 t=12.33 (one stream's loss adds 1.67 ticks to the average under HTTP/2; the tail t=14 is the lost stream itself, same either way)
```
Under HTTP/2's single ordered TCP stream, the loss holds back streams 1 and 2 even though their data arrived; under HTTP/3's independent QUIC streams, only the lost stream waits. The tail (the lost stream) is the same either way — HOL blocking hurts the *other* streams, which is exactly what multiplexing was meant to protect. The edge protocols are from live `curl -sI` probes.

## Related
098-tcp-vs-udp.md, 100-grpc.md, 048-cdn.md, 071-tls.md, 028-connection-pooling.md, 014-idempotency.md

## Sources
- RFC 9113, "HTTP/2": https://www.rfc-editor.org/rfc/rfc9113.html
- RFC 9114, "HTTP/3", and RFC 9000, "QUIC: A UDP-Based Multiplexed and Secure Transport": https://www.rfc-editor.org/rfc/rfc9114.html
