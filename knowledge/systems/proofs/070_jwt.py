"""JWT validation and key rotation, with the real PyJWT library against a naive hand-rolled verifier.
A. `alg: none`: a verifier that trusts the header's alg accepts an unsigned forgery; pinning algorithms rejects it.
B. Audience: a token minted for another app is accepted unless `aud` is pinned.
C. Rotation: keys looked up by `kid` let old and new keys overlap, then retire; a single static key either never
   rotates or breaks every live token the moment it changes."""
import base64
import hashlib
import hmac
import json
import time

import jwt  # PyJWT

OLD, NEW = b"old-signing-key-0123456789abcdef!", b"new-signing-key-0123456789abcdef!"


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def naive_verify(token, key):
    """Trusts the header's alg, as early libraries did."""
    head, body, sig = token.split(".")
    alg = json.loads(base64.urlsafe_b64decode(head + "=="))["alg"]
    if alg == "none":
        return json.loads(base64.urlsafe_b64decode(body + "=="))
    want = base64.urlsafe_b64encode(hmac.new(key, f"{head}.{body}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return json.loads(base64.urlsafe_b64decode(body + "==")) if hmac.compare_digest(want, sig) else None


forged = b64({"alg": "none", "typ": "JWT"}) + "." + b64({"sub": "attacker", "role": "admin", "aud": "factory"}) + "."
print(f"A  naive verifier, alg=none forgery: {naive_verify(forged, OLD)}")
try:
    jwt.decode(forged, OLD, algorithms=["HS256"], audience="factory")
except jwt.InvalidTokenError as e:
    print(f"A  PyJWT, algorithms=['HS256']:     rejected ({type(e).__name__})")

other_app = jwt.encode({"sub": "operator", "aud": "billing", "exp": time.time() + 600}, OLD, algorithm="HS256")
print(f"B  aud not checked: {jwt.decode(other_app, OLD, algorithms=['HS256'], options={'verify_aud': False})['aud']!r} accepted")
try:
    jwt.decode(other_app, OLD, algorithms=["HS256"], audience="factory")
except jwt.InvalidAudienceError:
    print("B  aud pinned to 'factory': rejected (InvalidAudienceError)")

keys = {"k1": OLD, "k2": NEW}
live = [jwt.encode({"sub": f"s{i}", "exp": time.time() + 600}, OLD, algorithm="HS256", headers={"kid": "k1"}) for i in range(5)]
fresh = jwt.encode({"sub": "new", "exp": time.time() + 600}, NEW, algorithm="HS256", headers={"kid": "k2"})


def by_kid(token, keyset):
    kid = jwt.get_unverified_header(token).get("kid")
    if kid not in keyset:  # kid only selects from our own set; it never names a file or URL
        return False
    try:
        jwt.decode(token, keyset[kid], algorithms=["HS256"])
        return True
    except jwt.InvalidTokenError:
        return False


def static(token, key):
    try:
        jwt.decode(token, key, algorithms=["HS256"])
        return True
    except jwt.InvalidTokenError:
        return False


print(f"C  overlap (k1 and k2 both trusted): old tokens valid {sum(by_kid(t, keys) for t in live)}/5, new valid {by_kid(fresh, keys)}")
print(f"C  after retiring k1:                 old tokens valid {sum(by_kid(t, {'k2': NEW}) for t in live)}/5, new valid {by_kid(fresh, {'k2': NEW})}")
print(f"C  single static key swapped to NEW:  old tokens valid {sum(static(t, NEW) for t in live)}/5 at the instant of rotation")
