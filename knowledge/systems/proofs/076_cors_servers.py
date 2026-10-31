"""CORS lab. Attacker page at http://127.0.0.1:8801/probe tries to read, from the visitor's browser:
- the real factory adapter at http://localhost:7654/heartbeat (no CORS headers: read must be blocked),
- a misconfigured service at http://localhost:8803 that reflects any Origin with credentials, and one that sends '*'."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROBE = """<pre id=o></pre><script>
const out = [];
async function tryRead(label, url, opts) {
  try { const r = await fetch(url, opts); out.push(label + ": READ " + (await r.text()).slice(0, 60)); }
  catch (e) { out.push(label + ": blocked (" + e.message + ")"); }
}
(async () => {
  await tryRead("factory adapter /heartbeat, no CORS", "http://localhost:7654/heartbeat");
  await tryRead("service reflecting Origin + credentials", "http://localhost:8803/reflect", {credentials: "include"});
  await tryRead("service sending ACAO *", "http://localhost:8803/star");
  o.textContent = out.join("\\n");
})();
</script>"""


class Attacker(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(PROBE.encode())

    def log_message(self, *a):
        pass


class Misconfigured(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if self.path == "/reflect":
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", ""))
            self.send_header("Access-Control-Allow-Credentials", "true")
        else:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"internal": "run tasks, PR links, heartbeat"}).encode())

    def log_message(self, *a):
        pass


threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8801), Attacker).serve_forever, daemon=True).start()
ThreadingHTTPServer(("127.0.0.1", 8803), Misconfigured).serve_forever()
