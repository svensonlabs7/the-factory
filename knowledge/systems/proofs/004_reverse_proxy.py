"""Reverse proxies: the X-Forwarded-For trust bug, with real HTTP servers on loopback.

A reverse proxy terminates the client connection, so the backend's socket peer is the PROXY, not the client.
To recover the real client IP the proxy adds X-Forwarded-For (XFF). The trap: XFF is just a header, so a
client can send its own. If the proxy forwards the client's XFF unchanged and the app trusts the leftmost
value, the client spoofs any IP it likes -> an IP-based control is bypassed.

Backend: allows a request only if the client IP (leftmost XFF) is in an internal allowlist.
- naive proxy  : forwards the client's XFF untouched  -> client spoofs 10.0.0.9 and is allowed (FAIL).
- correct proxy: strips the client's XFF, sets XFF to the real peer IP -> spoof denied (FIX).
Deterministic; all 127.0.0.1."""
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

INTERNAL = {"10.0.0.9"}  # the IP range an IP-based control would trust


class Backend(BaseHTTPRequestHandler):
    def do_GET(self):
        xff = self.headers.get("X-Forwarded-For", "")
        client_ip = xff.split(",")[0].strip()  # app trusts the LEFTMOST value (the bug)
        allowed = client_ip in INTERNAL
        self.send_response(200 if allowed else 403)
        self.end_headers()
        self.wfile.write(f"{'ALLOW' if allowed else 'DENY'} client_ip={client_ip!r}".encode())

    def log_message(self, *a):
        pass


def make_proxy(backend_port, strip_client_xff):
    class Proxy(BaseHTTPRequestHandler):
        def do_GET(self):
            peer = self.client_address[0]  # the real TCP peer of THIS hop
            if strip_client_xff:
                xff = peer                                   # correct: proxy owns XFF
            else:
                client = self.headers.get("X-Forwarded-For")  # naive: trust/forward what the client sent
                xff = f"{client}, {peer}" if client else peer
            req = urllib.request.Request(f"http://127.0.0.1:{backend_port}/", headers={"X-Forwarded-For": xff})
            try:
                with urllib.request.urlopen(req) as r:
                    body, code = r.read(), r.status
            except urllib.error.HTTPError as e:  # relay the backend's 4xx instead of crashing
                body, code = e.read(), e.code
            self.send_response(code)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    return Proxy


def serve(handler):
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


backend = serve(Backend)
bport = backend.server_address[1]


def attack(strip):
    proxy = serve(make_proxy(bport, strip))
    pport = proxy.server_address[1]
    # The client spoofs an internal IP in its own XFF header.
    req = urllib.request.Request(f"http://127.0.0.1:{pport}/", headers={"X-Forwarded-For": "10.0.0.9"})
    try:
        with urllib.request.urlopen(req) as r:
            out = f"HTTP {r.status}: {r.read().decode()}"
    except urllib.error.HTTPError as e:
        out = f"HTTP {e.code}: {e.read().decode()}"
    proxy.shutdown()
    return out


print(f"naive proxy (forwards client XFF): {attack(strip=False)}")
print(f"correct proxy (overwrites XFF)   : {attack(strip=True)}")
backend.shutdown()
