"""OAuth: a toy authorization server, in process, to show RFC 9700's two main defences.
A. Authorization code interception: without PKCE, whoever holds the code gets the token. With PKCE (S256), the code
   alone is useless; the token endpoint also needs the verifier that only the real client has.
B. Redirect URI matching: prefix matching sends codes to a look-alike host; exact matching refuses it."""
import base64
import hashlib
import secrets

REGISTERED = "https://app.example.com/callback"


class AuthServer:
    def __init__(self, exact_redirects=True):
        self.codes, self.exact = {}, exact_redirects

    def authorize(self, redirect_uri, challenge=None):
        ok = redirect_uri == REGISTERED if self.exact else redirect_uri.startswith("https://app.example.com")
        if not ok:
            return None, "error: redirect_uri not registered"
        code = secrets.token_urlsafe(16)
        self.codes[code] = challenge
        return code, f"302 -> {redirect_uri}?code=..."

    def token(self, code, verifier=None):
        if code not in self.codes:
            return "error: invalid_grant"
        challenge = self.codes.pop(code)
        if challenge is not None:
            if verifier is None or s256(verifier) != challenge:
                return "error: invalid_grant (PKCE verifier mismatch)"
        return "access_token issued"


def s256(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


# A: the attacker sees the code (a log, a leaky redirect, a malicious app on the device) and redeems it first.
server = AuthServer()
code, _ = server.authorize(REGISTERED)
print(f"A  no PKCE:   attacker redeems the stolen code -> {server.token(code)}")
verifier = secrets.token_urlsafe(48)
code, _ = server.authorize(REGISTERED, challenge=s256(verifier))
print(f"A  with PKCE: attacker redeems the stolen code -> {server.token(code)}")
code, _ = server.authorize(REGISTERED, challenge=s256(verifier))
print(f"A  with PKCE: real client with its verifier    -> {server.token(code, verifier)}")

# B: the attacker starts a flow with a redirect_uri on a host they control.
evil = "https://app.example.com.attacker.net/callback"
for label, exact in (("prefix matching", False), ("exact matching ", True)):
    _, result = AuthServer(exact_redirects=exact).authorize(evil)
    print(f"B  {label}: redirect_uri={evil} -> {result}")
