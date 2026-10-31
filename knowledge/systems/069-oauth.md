# 69. OAuth

Track: B. Security · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)\boauth|\boidc\b|redirect_uri|scope=|claude_code_oauth_token|gh auth`

## What it is
OAuth 2.0 lets a user grant an application limited access to their account on another service without sharing their password. The user signs in at an authorization server. The app receives a short authorization code at a registered redirect URI and exchanges it for an access token, plus optionally a refresh token, that is scoped to what was approved. Access tokens are usually bearer tokens: whoever holds one can use it, so they should be short-lived, narrowly scoped, kept out of URLs and logs, and revocable.

RFC 9700 (2025) is the current security baseline:
- the authorization-code flow with PKCE;
- exact matching of redirect URIs;
- no implicit grant and no password grant;
- audience- and scope-restricted tokens;
- sender-constrained tokens, or rotating refresh tokens for public clients.

OpenID Connect (OIDC) adds identity (who the user is) on top of OAuth.

## When it is worth it
Use OAuth or OIDC whenever an app acts on a user's behalf at another service, or delegates sign-in to an identity provider. Never build an authorization server yourself: use the provider's, or a vetted library. A machine-to-machine integration with a single owner needs only a narrowly scoped token or the client-credentials grant, not user consent flows. Sender-constrained tokens (mTLS, DPoP) are for high-value APIs with many clients. One operator holding a few tokens needs scoping, safe storage and a written rotation path.

## How it fails
- **Code interception without PKCE:** a malicious app or a leaky log sees the authorization code → it redeems the code first and gets the token.
- **Loose redirect matching:** the server accepts any redirect URI that starts with the registered host → codes are sent to `app.example.com.attacker.net`.
- **Implicit grant:** tokens are returned in the URL fragment → they leak through history, referrers and logs.
- **Over-scoped, long-lived bearer tokens:** a token with every scope and no expiry leaks once → full, lasting access.
- **Tokens in URLs or logs:** query strings and debug output keep tokens where others can read them.
- **No rotation path:** nobody knows every place a token is stored → after a leak it stays live while people search for where to change it.

## Review checklist
- [ ] **Does a new OAuth client use authorization code with PKCE (S256)?** · Applies when: the diff adds a user-facing OAuth or OIDC sign-in or a delegated-access flow. · Block if: it uses the implicit or password grant, or the code flow without PKCE, or `plain` instead of `S256`.
- [ ] **Are redirect URIs registered and matched exactly?** · Applies when: the diff configures redirect URIs or validates them. · Block if: matching uses prefixes, wildcards or patterns.
- [ ] **Does each token carry only the scopes the job needs?** · Applies when: the diff requests scopes or creates a token for a workload. · Block if: it requests broad scopes the code never uses.
- [ ] **Do tokens stay out of URLs, logs and client storage?** · Applies when: the diff handles access or refresh tokens. · Block if: a token is put in a query string, logged, or stored in browser storage readable by scripts.
- [ ] **Is there a written way to rotate and revoke it?** · Applies when: the diff adds a long-lived token or secret. · Block if: nothing records where it is stored and how to revoke and replace it.

## In the factory
- The factory implements no OAuth flow (grep finds no `authorize`, `redirect_uri`, `code_verifier` or token exchange). It only holds bearer tokens issued by others: the Claude Code OAuth token (`.env`, and a CI secret for the gate), the `gh` CLI's OAuth token (keychain), and Cloudflare Access sessions for the dashboard, whose sign-in Cloudflare runs. Building any flow here would be over-engineering.
- `factory/intake/README.md:83`, `infra/cloudflare-tunnel/README.md:72`: rotation is written down for the webhook secret (with a previous value accepted during the switch) and for the Grok Bot Access token. Right.
- Gap (low): no written rotation and revocation path for the Claude Code OAuth token or the `gh` token, though both are long-lived bearer tokens stored in more than one place (see GAPS.md).
- The scope of the `gh` token is part of 68. IAM, which is deferred.

## Proof
`python3 -I knowledge/systems/proofs/069_oauth.py`, a toy authorization server in one process:
```
A  no PKCE:   attacker redeems the stolen code -> access_token issued
A  with PKCE: attacker redeems the stolen code -> error: invalid_grant (PKCE verifier mismatch)
A  with PKCE: real client with its verifier    -> access_token issued
B  prefix matching: redirect_uri=https://app.example.com.attacker.net/callback -> 302 -> https://app.example.com.attacker.net/callback?code=...
B  exact matching : redirect_uri=https://app.example.com.attacker.net/callback -> error: redirect_uri not registered
```

## Related
067-secrets-management.md, 070-jwt-rotation.md, 077-csrf.md, 071-tls.md

## Sources
- RFC 9700, "Best Current Practice for OAuth 2.0 Security": https://www.rfc-editor.org/rfc/rfc9700.html
- RFC 7636, "Proof Key for Code Exchange by OAuth Public Clients": https://www.rfc-editor.org/rfc/rfc7636.html
