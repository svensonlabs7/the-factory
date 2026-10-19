# 77. CSRF

Track: B. Security · Status: proven · Updated: 2026-10-18

## What it is
Cross-site request forgery (CSRF) is when another website makes a logged-in user's browser send a request to your site. The browser attaches that user's cookies automatically, so your site sees an authenticated request the user never meant to make: a transfer, a delete, a settings change. It only works against ambient credentials, meaning cookies and browser-managed auth. A request authenticated by a header the client must add itself (an `Authorization` token, an HMAC signature, a custom header) cannot be forged this way. A cross-site page cannot set such a header without a CORS preflight the server would have to approve.

Defences for cookie-authenticated, state-changing routes:
- **Primary:** a CSRF token (synchronizer or signed double-submit), checks on `Sec-Fetch-Site` or `Origin`, and never changing state on GET.
- **Second layer:** `SameSite=Lax` or `Strict` cookies.

XSS defeats all of them.

## When it is worth it
Whenever a site uses cookies, or any credential the browser sends by itself, to authorize a request that changes state. APIs authenticated only by headers or signatures, with no permissive CORS, are not exposed and need no CSRF tokens. Adding tokens there is ceremony. Read-only GET routes behind a cookie need nothing except to stay read-only.

## How it fails
- **Cookie session, no CSRF defence:** an attacker page auto-submits a form to `/transfer` → the browser attaches the session cookie → the transfer happens.
- **Relying on default SameSite:** the cookie has no `SameSite` attribute, and Chrome's "Lax-allowing-unsafe" rule still sends it on cross-site POSTs for two minutes after it is set → forged POSTs succeed right after login.
- **State change on GET:** `GET /delete?id=1` → a link or a top-level navigation from another site sends even `SameSite=Lax` cookies → the delete happens.
- **Permissive CORS:** `Access-Control-Allow-Origin: *` or a reflected origin, with credentials → cross-site scripts can send custom headers and read responses, which defeats the header defence.
- **Sibling subdomain:** a compromised `evil.example.com` is "same-site" with `app.example.com`, so SameSite does not stop it.

## Review checklist
- [ ] **Does a cookie-authenticated route that changes state check for CSRF?** · Applies when: the diff adds or changes a POST, PUT, PATCH or DELETE route authorized by cookies or other browser-sent credentials. · Block if: it has no CSRF token and no `Sec-Fetch-Site` or `Origin` check.
- [ ] **Do GET routes stay free of side effects?** · Applies when: the diff adds or changes a GET or HEAD route. · Block if: it creates, changes or deletes anything, or starts paid work.
- [ ] **Do session cookies set SameSite explicitly?** · Applies when: the diff sets a cookie used for authentication. · Block if: `SameSite` is missing, or set to `None` without a stated cross-site need.
- [ ] **Is CORS limited to trusted origins?** · Applies when: the diff adds CORS headers or middleware. · Block if: it allows any origin, or reflects the request's origin, together with credentials or custom auth headers.

## In the factory
- `factory/intake/webhook_adapter.py:588`: the only state-changing route, `POST /trigger`, is authorized by an HMAC header (`X-Hub-Signature-256` with `X-Factory-Timestamp`), not a cookie, so CSRF cannot reach it. Right.
- No CORS middleware anywhere in the adapter, so a cross-site script cannot send that header: the preflight goes unanswered. Right.
- `infra/cloudflare-tunnel/config.yml:5-9`: the cookie-authenticated hostname (`dash.`, behind an Access email login) routes only `GET /command` and `/command/data`. `/trigger` is not routed there, and those GETs are read-only. Right.
- Every GET route (`/status`, `/health`, `/heartbeat`, `/command`, `/command/data`) is free of side effects. `/command/data` calls `gh` to read PR state, cached 60 s. Right.
- Not applicable at today's load: CSRF tokens. No cookie-authenticated route changes state.

## Proof
A victim server on `http://localhost:8802` and an attacker on `http://127.0.0.1:8801` (a different site), driven in the browser pane. The victim's `/login` sets `lax` (`SameSite=Lax`) and `legacy` (no SameSite). The victim's log after the attacks:
```
POST /transfer   (attacker auto-submitted form)    cookies: ["legacy"]          Sec-Fetch-Site: cross-site
GET /delete      (attacker top-level navigation)   cookies: ["lax", "legacy"]   Sec-Fetch-Site: cross-site
OPTIONS /trigger (attacker fetch with X-Sig header) requested headers: x-sig     -> no CORS answer
```
The attacker page's fetch reported `blocked: Failed to fetch`, and the `POST /trigger` never arrived. In short:
- a cookie with no SameSite was sent on a cross-site POST, an explicit `Lax` cookie was not;
- both were sent on a cross-site GET navigation;
- a custom-header request, the factory's model, never left the browser.

## Related
079-xss.md, 076-cors.md, 101-webhooks.md, 069-oauth.md, 067-secrets-management.md, 022-websockets.md

## Sources
- "Cross-Site Request Forgery Prevention Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- "Set-Cookie: SameSite", MDN: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#samesitesamesite-value
