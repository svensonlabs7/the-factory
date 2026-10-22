# 98. TCP vs UDP

Track: J. Networking · Status: proven · Updated: 2026-10-19

## What it is
TCP and UDP are the two transport protocols over IP. **TCP** gives "a reliable, in-order, byte-stream service" (RFC 9293): it sets up a connection, numbers every byte, retransmits what is lost, drops duplicates, and reorders what arrives out of order, so the application reads exactly the bytes that were sent, in order. The cost is that boundaries disappear — "TCP guarantees no correlation between the boundaries of TCP segments sent and received", so three `send()` calls can arrive as one `recv()` or be split across several. **UDP** is a thin wrapper over IP: one datagram in, one datagram out, with "delivery and duplicate protection … not guaranteed" (RFC 768) and no ordering and no connection. A UDP datagram keeps its boundary, but it may be lost, duplicated or reordered, and nothing recovers it. Applications that need reliability over UDP must build it themselves (as QUIC and DNS-over-UDP-with-retry do).

## When it is worth it
- **TCP** is the default for almost everything: HTTP, SSH, database connections, anything where every byte must arrive in order. Pick it unless you have a specific reason not to.
- **UDP** is worth it when per-message latency beats completeness, or when you want to build your own delivery semantics: DNS (one small request/response, cheaper than a handshake), real-time media and games (a late packet is worthless, so do not wait for a retransmit), QUIC/HTTP/3 (reliability and multiplexing moved into userspace to escape TCP head-of-line blocking — 099-http2-http3.md), and VPN/tunnel transports.
- Reaching for UDP for a normal request/response service is over-engineering: you reimplement retransmission, ordering, congestion control and framing that TCP already gives you, and usually worse.

## How it fails
- **Treating a TCP stream as messages:** reading one `recv()` and assuming it is one application message. Two messages coalesce, or one splits, and the parser corrupts or stalls (proof B). The fix is framing: a length prefix or a delimiter.
- **Partial reads/writes ignored:** assuming one `recv`/`send` moves the whole payload; a large message needs a loop until the expected length (or EOF).
- **UDP used where loss is intolerable:** a datagram is dropped and never retransmitted, so the receiver silently misses data and must detect the gap itself (proof A).
- **UDP reordering/duplication unhandled:** datagrams arrive in a different order or twice, and the app acts on stale or repeated data because it added no sequence numbers.
- **Datagram too large:** a UDP payload past the path MTU is fragmented (more loss risk) or dropped; TCP segments to the MSS automatically.
- **Head-of-line blocking on TCP:** one lost segment stalls every byte behind it in that connection, even bytes that already arrived, because the stream must stay in order. Multiplexing many logical streams onto one TCP connection shares that stall (099-http2-http3.md).

## Review checklist
- [ ] **Is a TCP byte stream framed before it is parsed as messages?** · Applies when: the diff reads from a raw TCP socket (not an HTTP/library client that already frames). · Block if: it treats one `recv()` as one message, with no length prefix, delimiter or read-loop, so coalesced or split reads corrupt the parse.
- [ ] **Does UDP code tolerate loss, reordering and duplication?** · Applies when: the diff sends or receives UDP datagrams. · Block if: correctness assumes every datagram arrives once and in order, with no sequence numbers, acks/retransmit, or idempotent handling.
- [ ] **Is UDP chosen for a reason TCP cannot serve?** · Applies when: the diff picks UDP for a new protocol or service. · Block if: the traffic is ordinary request/response that needs reliability, and UDP is used without a latency or custom-semantics reason — reimplementing TCP badly.
- [ ] **Are partial reads and writes handled?** · Applies when: the diff moves a payload whose size can exceed one segment over a stream socket. · Block if: it assumes a single `send`/`recv` transfers the whole payload.

## In the factory
- The factory speaks no raw sockets. Every network hop is TCP through a library that frames for it, so the "stream is not messages" bug cannot occur here:
  - the adapter is `uvicorn` over HTTP (`factory/intake/com.svenson.factory-intake.plist:14,18`), bound to `127.0.0.1:7654`; HTTP carries its own framing (`Content-Length`/chunked).
  - the Cloudflare Tunnel, `gh`, and the sandbox egress proxy (`factory/build/egress/tinyproxy.conf`: `ConnectPort 443`) are all TCP/TLS.
  - the only UDP in the path is DNS, handled by the resolver, not the factory (097-dns.md).
- So TCP-vs-UDP is a protocol the factory consumes, not one it implements. Right: a webhook adapter and a dashboard are exactly the ordered-reliable request/response that TCP is the default for; UDP would be a mistake here.
- TCP head-of-line blocking is latent but harmless at this load: one operator, few concurrent requests, no stream multiplexing. It becomes relevant only if a future multiplexed protocol (HTTP/2, gRPC — 099, 100) runs over a lossy link, not on loopback.
- Not applicable at today's load: custom UDP protocols, QUIC, framing libraries, MTU tuning.

## Proof
`python3 knowledge/systems/proofs/098_tcp_udp.py`, real kernel sockets on `127.0.0.1`:
```
A  UDP: sent [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
A  UDP: received [0, 2, 4, 5, 7, 9]  -> 4 datagram(s) lost for good [1, 3, 6, 8], no retransmit
B  TCP: three sends [b'AAAA', b'BBBB', b'CCCC']; first recv returned b'AAAABBBBCCCC' (multiple messages merged -> boundaries gone)
B  TCP: full stream b'AAAABBBBCCCC' -> in order and complete (= concatenation of the sends)
```
A sends ten numbered datagrams through a relay that drops ~30%; the receiver gets only six, and the four lost are gone with no recovery. B makes three `send()` calls of distinct messages; one `recv()` returns all twelve bytes concatenated — the message boundaries are gone, though the stream is in order and complete. The fix is length-prefix framing.

## Related
097-dns.md, 099-http2-http3.md, 100-grpc.md, 028-connection-pooling.md, 071-tls.md, 011-timeouts.md

## Sources
- RFC 768, "User Datagram Protocol": https://www.rfc-editor.org/rfc/rfc768.txt
- RFC 9293, "Transmission Control Protocol (TCP)" (§2.2, §3.7): https://www.rfc-editor.org/rfc/rfc9293.html
