# 80. SSRF

Track: B. Security · Status: proven · Updated: 2026-10-18

## What it is
Server-side request forgery (SSRF) is when an attacker makes your server send a request to a place they choose. The server sits inside your network, so it can reach what the attacker cannot: cloud metadata (`169.254.169.254`, which hands out credentials), admin ports on localhost, databases and internal APIs. The classic entry is a URL parameter: "fetch this image", "call this webhook". The modern entry is an AI agent that makes requests on behalf of text an attacker controls.

OWASP splits it in two:
- **The server only needs a few known destinations:** allow-list them, and enforce the list at the network layer too.
- **The server must call arbitrary URLs:** resolve the host, check every resolved IP against private, loopback, link-local and metadata ranges, connect only to that checked IP, and refuse redirects.

String deny-lists fail, because one address has many spellings: decimal, hex, short forms, IPv6-mapped.

## When it is worth it
It matters wherever a server, job or agent makes network requests whose destination, or whose content, is shaped by input it does not fully trust. That includes LLM agents given untrusted tasks. Network egress allow-lists are cheap and the strongest control, so use them whenever the set of needed destinations is known. Application-layer URL validation is only needed when users legitimately supply destinations (webhook targets, link previews). If the server never fetches user-chosen URLs and its sandbox has an egress allow-list, per-request URL validation is redundant.

## How it fails
- **User-supplied URL fetched as is:** `?url=http://169.254.169.254/...` → the server returns its own cloud credentials.
- **Deny-list bypass:** the code blocks the string "169.254.169.254" → `http://2852039166/` and `http://0xA9FEA9FE/` reach the same address.
- **DNS rebinding:** the host is checked when it resolves to a public IP, then re-resolves to an internal one at connect time.
- **Redirect follow:** an allowed URL answers `302` to an internal address, and the client follows it.
- **Filter on one path only:** egress rules cover forwarded traffic but not traffic to the host or VM the sandbox runs on → the sandbox reaches the host's own services.
- **Agent as the request maker:** a prompt-injected agent with open egress sends secrets or probes internal services.

## Review checklist
- [ ] **Does any request go to a destination built from untrusted input?** · Applies when: the diff adds an HTTP, socket or tool call whose host, URL or port comes from a request, a task, a payload or model output. · Block if: the destination is not checked against an allow-list, or against resolved-IP checks when arbitrary hosts are a requirement.
- [ ] **Is the check on the resolved IP, not the string?** · Applies when: the diff validates a URL or host. · Block if: it matches strings or regexes against the URL instead of parsing and resolving it and checking the IP (private, loopback, link-local, metadata).
- [ ] **Are redirects off, or re-checked?** · Applies when: the diff fetches a URL that passed validation. · Block if: the client follows redirects without validating each hop.
- [ ] **Does a sandbox or agent have egress limited at the network layer?** · Applies when: the diff adds or changes a sandbox, container or job that runs untrusted code or an agent. · Block if: its network reaches arbitrary hosts, or the egress rules leave the host or VM it runs on reachable.
- [ ] **Do internal services listen only where they must?** · Applies when: the diff adds a listening service on a host that also runs sandboxes. · Block if: it binds to all interfaces when localhost would do.

## In the factory
- `factory/build/egress/allow`, `factory/build/egress/tinyproxy.conf`: the sandbox reaches only four anchored hostnames (Claude's API, npm, PyPI), on port 443, through a default-deny proxy. This is OWASP's allow-list case. Right.
- `factory/build/egress.sh:23-30`: a `DOCKER-USER` firewall chain lets only the proxy leave the subnet, and every run proves it first. Right: the proof blocked the internet and the Mac's services (`192.168.5.2:5000`, `:53`).
- `factory/intake/com.svenson.factory-intake.plist:21`: the adapter binds `127.0.0.1` only. Right.
- The adapter never fetches a user-chosen URL. Its only outbound calls are `git` and `gh` against the configured origin, and PR URLs come from `gh`'s own output, so no URL validation is needed there.
- Gap: `DOCKER-USER` filters only forwarded traffic, so a sandbox container can open the Colima VM's own `sshd` (`172.30.0.1:22`) (see GAPS.md).
- Known and documented in `factory/build/README.md`: DNS lookups still go through Docker's resolver, a low-bandwidth way out.

## Proof
From a throwaway container on the real `factory-sandbox` network, using egress.sh's pinned curl image:
```
1 direct internet (https://example.com):       blocked (Failed to connect)
2 Mac via Colima host (192.168.5.2:5000):      blocked (Failed to connect)
3 Mac DNS forwarder (192.168.5.2:53 tcp):       blocked (Failed to connect)
4 Colima VM gateway (172.30.0.1:22 ssh):        CONNECTED
5 proxy CONNECT to Mac (192.168.5.2:443):       000
6 proxy plain HTTP to Mac (http://192.168.5.2:5000): 403
7 proxy to an allowed host (api.anthropic.com):  401
```
The VM listens on `0.0.0.0:22` (key-only: `passwordauthentication no`) and on DNS for localhost and `192.168.5.1`. There is no Docker API on TCP.

Deny-list bypass (`python3 -I`, standard library only):
```
http://169.254.169.254/latest/meta-data  naive blocklist allows: False resolves to: 169.254.169.254
http://2852039166/latest/meta-data       naive blocklist allows: True  resolves to: 169.254.169.254
http://0xA9FEA9FE/                       naive blocklist allows: True  resolves to: 169.254.169.254
http://127.1/                            naive blocklist allows: True  resolves to: 127.0.0.1
http://[::ffff:169.254.169.254]/         naive blocklist allows: False resolves to: 169.254.169.254
```
Checking the resolved IP with `ipaddress` (`is_private or is_link_local or is_loopback`) flags all five.

## Related
067-secrets-management.md, 101-webhooks.md, 074-waf.md, 097-dns.md, 007-docker.md

## Sources
- "Server-Side Request Forgery Prevention Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- "A10:2021 Server-Side Request Forgery", OWASP Top 10: https://top10.owasp.org/A10_2021-Server-Side_Request_Forgery_%28SSRF%29
