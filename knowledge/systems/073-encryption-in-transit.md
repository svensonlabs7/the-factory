# 73. Encryption in Transit

Track: B. Security · Status: proven · Updated: 2026-10-18

Triggers: files `^infra/cloudflare-tunnel/|^factory/build/egress` · lines `(?i)\bhttp://|\bws://|connectport|plaintext`

## What it is
Encryption in transit means data is encrypted on every network hop where someone other than you could read or change it: Wi-Fi, ISPs, cloud networks, shared VLANs, other tenants. In practice that is TLS for HTTP, git and APIs, QUIC (TLS 1.3 built in) for tunnels, and SSH. Encryption hides content, not metadata. An on-path observer still sees who talks to whom, when and how much, and with TLS also the server name (SNI), unless Encrypted Client Hello is in use. A hop may stay plaintext only where nobody else can observe it: loopback on one machine, or inside an already-encrypted tunnel.

## When it is worth it
Every hop that leaves a machine or crosses a network you do not fully control needs it, at any scale. That includes "internal" service-to-service traffic in a cloud network. Re-encrypting loopback or same-host hops is over-engineering. Mutual TLS between services, service meshes and Encrypted Client Hello are worth it when many services share a network or metadata itself is sensitive.

## How it fails
- **Plaintext on a shared network:** a token or password in an HTTP header or body is readable by anything on the path.
- **TLS terminated, then plaintext onward:** a proxy or load balancer decrypts and forwards over plaintext across a network.
- **"Internal" assumed safe:** service-to-service HTTP inside a VPC or cluster → a single compromised neighbour reads everything.
- **Metadata leak:** SNI, DNS and CONNECT lines reveal which hosts are contacted, even when content is encrypted.
- **Unencrypted fallback:** a client silently retries over plaintext when TLS fails.

## Review checklist
- [ ] **Is every hop that leaves the machine encrypted?** · Applies when: the diff adds a network connection, endpoint, proxy hop or service-to-service call. · Block if: data crosses a network other than loopback over plaintext (HTTP, raw TCP, unencrypted database or queue protocols).
- [ ] **Where TLS terminates, is the onward hop protected?** · Applies when: the diff adds a proxy, tunnel, load balancer or edge in front of a service. · Block if: the decrypted traffic travels on across a network in plaintext.
- [ ] **Is there no silent plaintext fallback?** · Applies when: the diff adds a client that can choose between TLS and plaintext. · Block if: it falls back to plaintext on a TLS error instead of failing.
- [ ] **Are secrets kept out of metadata?** · Applies when: the diff puts data into hostnames, URLs or DNS names. · Block if: a secret or personal data appears where TLS does not encrypt it (hostnames, SNI, DNS queries).

## In the factory
Hop by hop:
- **Grok Bot to Cloudflare's edge:** HTTPS, with a Let's Encrypt certificate. Right. The old TLS versions are the 071-tls.md gap.
- **Cloudflare's edge to cloudflared:** QUIC, which is TLS 1.3 by design. All 65 tunnel registrations in the cloudflared log say `protocol=quic`. Right.
- **cloudflared to the adapter:** `http://localhost:7654`, loopback only (`infra/cloudflare-tunnel/config.yml`). Right.
- **The adapter to GitHub:** `git` over `https://github.com/...` and `gh` over HTTPS. Right.
- **The host to the agent-server in the sandbox:** `http://127.0.0.1:<port>` forwarded into the Colima VM, so it never leaves the machine. Acceptable.
- **The sandbox to the egress proxy, then Claude's API:** the `CONNECT` line on the VM's Docker bridge shows the hostname, and the payload is TLS end to end to `api.anthropic.com`. Right.
- **CI runners to Claude's API, and image pulls:** HTTPS, with images pinned by digest. Right.
- Not applicable at today's load: mTLS between components and Encrypted Client Hello. Every cross-network hop is already TLS or QUIC, and the hostnames the factory contacts are not secret.

## Proof
`python3 -I knowledge/systems/proofs/073_on_path.py`: a local relay records every byte between client and server.
```
A  plain HTTP: observer captured 174 bytes; secret visible = True
B  TLS (TLSv1.2, server answered 'HTTP/1.1 200 OK'): observer captured 4792 bytes; secret visible = False; hostname 'github.com' visible = True
```
(The macOS system Python negotiated TLS 1.2 with github.com.) Tunnel protocol, from `~/Library/Logs/com.cloudflare.cloudflared.err.log`: `65 protocol=quic`. Git transport: `git remote get-url origin` is `https://github.com/svensonlabs7/the-factory.git`.

## Related
071-tls.md, 067-secrets-management.md, 080-ssrf.md, 097-dns.md, 072-encryption-at-rest.md

## Sources
- NIST SP 800-52 Rev. 2, "Guidelines for the Selection, Configuration, and Use of TLS Implementations": https://csrc.nist.gov/pubs/sp/800/52/r2/final
- RFC 9325, "Recommendations for Secure Use of TLS and DTLS": https://www.rfc-editor.org/rfc/rfc9325.html
- "Cloudflare Tunnel", Cloudflare documentation: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
