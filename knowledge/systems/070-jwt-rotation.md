# 70. JWT Rotation

Track: B. Security · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)\bjwt\b|\bjwks|cf-access-jwt|\bjose\b|pyjwt`

## What it is
A JSON Web Token (JWT) is a signed set of claims: who (`sub`), for whom (`aud`), from whom (`iss`), until when (`exp`). Anyone holding the verification key can check it without calling the issuer. Validation must be strict:
- pin the accepted algorithms, never trusting the token's own `alg` header, since `none` and RS256-to-HS256 confusion are classic forgeries;
- verify the signature;
- check `iss`, `aud` and `exp`;
- treat header fields such as `kid` as untrusted input.

Rotation means replacing signing keys on a schedule and at once after a leak, without breaking live tokens. The pattern: each token names its key with `kid`; verifiers fetch the issuer's published key set (JWKS) and pick the key by `kid`; old and new keys overlap for at least one token lifetime; then the old key is retired.

## When it is worth it
Validate JWTs wherever you accept them, at any scale. That includes tokens an edge proxy or identity provider adds for your origin to check. Issue your own JWTs only when stateless verification by other services is the point. For one service checking its own sessions, an opaque session ID in a store is simpler, and revocation is instant. Key rotation via a JWKS endpoint and `kid` is needed whenever keys are long-lived or shared with several verifiers. A single HMAC secret checked by one process can rotate with a simple "current plus previous" pair.

## How it fails
- **Trusting `alg`:** the verifier reads the algorithm from the token → an unsigned `alg: none` token, or an HS256 token signed with the public RSA key, is accepted.
- **No audience check:** a valid token minted for another app at the same issuer → accepted here.
- **No expiry check, or very long `exp`:** a stolen token works for months.
- **Hard-coded single key:** rotation breaks every live token at the switch, so nobody rotates, even after a leak.
- **Trusting `kid`, `jku` or `x5u`:** `kid` is used as a file path or SQL value, or `jku` points to an attacker's key set → injection or a forged signature.
- **Caching keys forever:** the issuer rotates (Cloudflare Access rotates about every 6 weeks) and the verifier rejects every new token.

## Review checklist
- [ ] **Are accepted algorithms pinned?** · Applies when: the diff verifies a JWT. · Block if: the algorithm list is missing, includes `none`, or is taken from the token's header.
- [ ] **Are `iss`, `aud` and `exp` checked?** · Applies when: the diff verifies a JWT. · Block if: any of the three is not validated against an expected value.
- [ ] **Does key lookup survive rotation?** · Applies when: the diff verifies tokens from an issuer that rotates keys. · Block if: the key is hard-coded or cached forever instead of selected by `kid` from the issuer's key set, refreshed on an unknown `kid`.
- [ ] **Are header fields treated as untrusted?** · Applies when: the diff reads `kid`, `jku` or `x5u`. · Block if: `kid` reaches a file path, query or command, or `jku`/`x5u` URLs are fetched without an allow-list.
- [ ] **Can a new signing secret overlap the old one?** · Applies when: the diff adds a signing key or HMAC secret. · Block if: only one key can be valid at a time.

## In the factory
- The factory issues no JWTs, and nothing in `factory/` parses one. Its own signed requests use an HMAC secret with a current-plus-previous rotation (`factory/intake/webhook_adapter.py:49`, `FACTORY_WEBHOOK_SECRET_PREVIOUS`), the same overlap model as `kid`-based rotation. Right.
- Cloudflare Access sits in front of both hostnames and adds a signed `Cf-Access-Jwt-Assertion` header to every request it lets through (`infra/cloudflare-tunnel/README.md`). Cloudflare rotates that key about every 6 weeks and keeps the previous one valid for 7 days.
- Decided not to validate it. The adapter cannot tell a request that passed Access from one that reached `localhost:7654` another way, but the Host check (076-cors.md) now closes the DNS-rebinding way, and what remains is a local process, which can already read `.env` and the logs. Validation would add a JWT library and a key fetch to block nothing new. Revisit if the adapter ever listens beyond localhost.
- Not applicable at today's load: issuing JWTs, or a JWKS endpoint of the factory's own.

## Proof
`uv run --with pyjwt python -I knowledge/systems/proofs/070_jwt.py`, using the real PyJWT library against a deliberately naive verifier:
```
A  naive verifier, alg=none forgery: {'sub': 'attacker', 'role': 'admin', 'aud': 'factory'}
A  PyJWT, algorithms=['HS256']:     rejected (InvalidAlgorithmError)
B  aud not checked: 'billing' accepted
B  aud pinned to 'factory': rejected (InvalidAudienceError)
C  overlap (k1 and k2 both trusted): old tokens valid 5/5, new valid True
C  after retiring k1:                 old tokens valid 0/5, new valid True
C  single static key swapped to NEW:  old tokens valid 0/5 at the instant of rotation
```

## Related
069-oauth.md, 067-secrets-management.md, 076-cors.md, 101-webhooks.md, 096-clock-skew.md

## Sources
- RFC 8725, "JSON Web Token Best Current Practices": https://www.rfc-editor.org/rfc/rfc8725.html
- "Validate JWTs", Cloudflare Zero Trust documentation: https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/
