"""CSRF lab. Victim at http://localhost:8802, attacker at http://127.0.0.1:8801 (a different site).
Victim: /login sets `lax` (SameSite=Lax) and `legacy` (no SameSite) cookies; POST /transfer and GET /delete change
state when a cookie arrives; POST /trigger needs a custom X-Sig header (like the factory's HMAC header) and sends no CORS.
Attacker: /form auto-submits a cross-site POST, /nav navigates top-level to GET /delete, /fetch tries the header route."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = []


class Victim(BaseHTTPRequestHandler):
    def _send(self, code, body, headers=()):
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def cookies(self):
        return sorted(c.split("=")[0].strip() for c in (self.headers.get("Cookie") or "").split(";") if "=" in c)

    def do_GET(self):
        if self.path == "/login":
            return self._send(200, "logged in", [("Set-Cookie", "lax=1; SameSite=Lax; Path=/"), ("Set-Cookie", "legacy=1; Path=/")])
        if self.path == "/delete":
            log.append({"route": "GET /delete", "cookies": self.cookies(), "site": self.headers.get("Sec-Fetch-Site")})
            return self._send(200, "deleted")
        if self.path == "/log":
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            return self.wfile.write(json.dumps(log).encode())
        self._send(404, "")

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        route = self.path
        log.append({"route": f"POST {route}", "cookies": self.cookies(), "x_sig": self.headers.get("X-Sig"),
                    "site": self.headers.get("Sec-Fetch-Site")})
        self._send(200 if route == "/transfer" or self.headers.get("X-Sig") else 401, "ok")

    def do_OPTIONS(self):  # a CORS preflight: no Access-Control-Allow-* headers, like the factory
        log.append({"route": f"OPTIONS {self.path}", "requested_headers": self.headers.get("Access-Control-Request-Headers")})
        self._send(405, "")

    def log_message(self, *a):
        pass


ATTACK = {
    "/form": '<form id=f method=POST action="http://localhost:8802/transfer"><input name=amount value=1000></form><script>f.submit()</script>',
    "/nav": '<script>location = "http://localhost:8802/delete"</script>',
    "/fetch": """<pre id=o>pending</pre><script>
fetch("http://localhost:8802/trigger", {method: "POST", headers: {"X-Sig": "forged"}, body: "{}", credentials: "include"})
  .then(r => o.textContent = "response " + r.status).catch(e => o.textContent = "blocked: " + e.message);</script>""",
}


class Attacker(BaseHTTPRequestHandler):
    def do_GET(self):
        body = ATTACK.get(self.path, "")
        self.send_response(200 if body else 404); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8801), Attacker).serve_forever, daemon=True).start()
ThreadingHTTPServer(("127.0.0.1", 8802), Victim).serve_forever()
