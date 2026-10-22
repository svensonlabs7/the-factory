# 75. DDoS Protection

Track: B. Security · Status: proven · Updated: 2026-10-18

## What it is
A distributed denial-of-service (DDoS) attack overwhelms a service with traffic from many sources until real users cannot get through. It comes in three kinds:
- **Volumetric floods** (layer 3/4: UDP reflection, SYN floods) that fill links;
- **Protocol and TLS exhaustion;**
- **Application-layer attacks** (layer 7): HTTP floods, expensive requests, slow connections that hold every worker.

A small origin cannot absorb any of these by itself, so the defence is architectural:
- hide the origin and accept traffic only from an edge network;
- let that anycast edge absorb and filter traffic (SYN cookies, request buffering, managed DDoS rules);
- cap what each request can cost the origin (timeouts, rate limits, concurrency limits, spend caps).

## When it is worth it
Any internet-reachable service needs a plan, because attacks are cheap to rent. For most services the plan is to put it behind a CDN or edge proxy with DDoS protection (on by default, often free), keep the origin unreachable except through that edge, and bound per-request cost. Scrubbing contracts, dedicated anti-DDoS services, multi-region absorption and custom traffic engineering are for large or high-value targets.

## How it fails
- **Origin IP exposed:** a DNS record, an old A record, an email header or a direct port reveals the server's address → attackers skip the edge and hit the origin directly.
- **Slow-connection exhaustion:** clients send requests very slowly and hold every connection slot → real requests are refused, at almost no bandwidth cost to the attacker.
- **Timeouts alone are not enough:** if slow connections arrive faster than slots ÷ timeout, the slots stay full anyway (Little's Law).
- **Expensive endpoints:** one request triggers heavy work (a build, a report, an LLM call) → a modest request rate exhausts CPU, money or quota ("denial of wallet").
- **Autoscaling without a cap:** the service scales to absorb an attack and the bill becomes the outage.

## Review checklist
- [ ] **Is the origin reachable only through the edge?** · Applies when: the diff adds a public service, DNS record, port or listening interface. · Block if: the origin answers on a public IP or hostname that bypasses the edge, or a DNS record exposes its address.
- [ ] **Is the per-request cost bounded?** · Applies when: the diff adds an endpoint that triggers heavy or paid work. · Block if: there is no rate limit, concurrency limit or daily cap on how much work callers can start.
- [ ] **Is connection holding bounded where no edge buffers?** · Applies when: the diff exposes a server without a buffering proxy in front. · Block if: it has no read or header timeout and no connection limit.
- [ ] **Does scaling have a cost ceiling?** · Applies when: the diff adds autoscaling or pay-per-use resources reachable from the internet. · Block if: there is no maximum.

## In the factory
- Public DNS for `factory.` and `dash.svensonlabs.dev` returns only Cloudflare anycast addresses (`whois`: `Cloudflare, Inc.`, `CLOUDFLARENET`). The tunnel's origin address does not appear in DNS. Right.
- `infra/cloudflare-tunnel/config.yml`: cloudflared makes outbound-only connections, so there is no inbound port on the Mac to flood, and the adapter listens on `127.0.0.1` only. Cloudflare's always-on layer 3–7 DDoS protection and its request buffering sit in front. Right.
- `factory/intake/webhook_adapter.py:72-73`: `MAX_PENDING` (5) and `MAX_RUNS_PER_DAY` (30) cap how much plan usage `/trigger` can start, even if the intake credential were abused, which bounds denial of wallet. The edge rate limit (5 per 10 s per IP) is in `infra/cloudflare-tunnel/README.md:42`. Right.
- Not applicable at today's load: dedicated anti-DDoS services, multi-region absorption and autoscaling. There is one origin, hidden behind an edge that already absorbs volumetric attacks.

## Proof
`dig` and `whois` against the live hostnames:
```
factory.svensonlabs.dev: 172.67.213.143 104.21.45.110 | 2606:4700:3034::6815:2d6e 2606:4700:3034::ac43:d58f
OrgName: Cloudflare, Inc.   NetName: CLOUDFLARENET
origin=2601:40:cb00… appears in DNS answers: 0
```
`python3 -I knowledge/systems/proofs/075_ddos.py`, simulated in virtual time with no network traffic. The origin has 20 slots. For 60 s, 5 slow connections a second (each 300 s long) arrive alongside 10 normal requests a second:
```
direct, no read timeout      normal requests served   38/600  (6%)
direct, 10 s read timeout    normal requests served   38/600  (6%)
direct, 2 s read timeout     normal requests served  600/600  (100%)
behind a buffering edge      normal requests served  600/600  (100%)
```
A 10 s timeout fails because 5/s × 10 s = 50 held slots, more than 20. A 2 s timeout works only while the attack rate stays below 10/s. The buffering edge works at any rate.

## Related
001-rate-limiting.md, 074-waf.md, 044-backpressure.md, 011-timeouts.md, 097-dns.md, 031-partitioning.md

## Sources
- "Mitigation techniques", AWS Best Practices for DDoS Resiliency: https://docs.aws.amazon.com/whitepapers/latest/aws-best-practices-ddos-resiliency/mitigation-techniques.html
- "Cloudflare DDoS Protection", Cloudflare documentation: https://developers.cloudflare.com/ddos-protection/
