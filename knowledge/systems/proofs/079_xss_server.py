"""Serve the real factory dashboard (command.html) with hostile /command/data, plus an innerHTML page for contrast.
Usage: python3 -I 079_xss_server.py <path to command.html> <port>"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

html_path, port = sys.argv[1], int(sys.argv[2])
PAYLOAD = '<img src=x onerror="window.__xss=(window.__xss||0)+1;document.title=\'PWNED\'">'
now = time.time()
DATA = {
    "now": now,
    "runs": [{
        "run_id": "<svg onload=window.__xss3=1>", "status": "blocked", "attempt": 2, "branch": "factory/x",
        "pr_url": "javascript:window.__xss2=1//pull/7", "queued_at": now - 600, "started_at": now - 590,
        "finished_at": now - 60, "blocking_reason": PAYLOAD, "error": None, "task": "Add a page " + PAYLOAD, "pr": None,
    }],
    "heartbeat": {"pipeline_status": PAYLOAD, "alive_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    "rejections": {"last_24h": {PAYLOAD: 3}, "last_hour": 1},
    "limits": {"max_pending": 5, "max_runs_per_day": 30, "max_retries": 2, "pending": 0, "runs_24h": 1},
}
UNSAFE = f"""<!doctype html><title>unsafe</title><div id=t></div>
<script>document.getElementById('t').innerHTML = {json.dumps("Task: " + PAYLOAD)};</script>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/command/data":
            body, ctype = json.dumps(DATA).encode(), "application/json"
        elif path == "/command":
            body, ctype = open(html_path, "rb").read(), "text/html; charset=utf-8"
        elif path == "/unsafe":
            body, ctype = UNSAFE.encode(), "text/html; charset=utf-8"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
