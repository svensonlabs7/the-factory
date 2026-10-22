"""Edge caching directives (RFC 5861, RFC 9111), with a real origin over HTTP and a small caching proxy in front.
The origin answers in 300 ms with `Cache-Control` set per test; it can be switched to return 503.
A. max-age only: the first request after expiry waits for the origin. stale-while-revalidate: it is answered from the
   stale copy at once while a background refresh runs.
B. Origin down (503) after expiry: without stale-if-error the client gets the 503; with it, the stale 200.
C. Vary: the origin varies by Accept-Language. A cache keyed on the URL alone serves the first language to everyone."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

STATE = {"cc": "max-age=1", "down": False, "version": 0}


class Origin(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        time.sleep(0.3)
        if STATE["down"]:
            self.send_response(503)
            self.end_headers()
            return
        STATE["version"] += 1
        lang = self.headers.get("Accept-Language", "en")
        body = f"v{STATE['version']} {'Hallo' if lang == 'de' else 'Hello'}".encode()
        self.send_response(200)
        self.send_header("Cache-Control", STATE["cc"])
        self.send_header("Vary", "Accept-Language")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{server.server_address[1]}/page"


def directive(cc, name):
    for part in cc.split(","):
        k, _, v = part.strip().partition("=")
        if k == name:
            return int(v)
    return 0


class EdgeCache:
    def __init__(self, honor_vary=True):
        self.store, self.honor_vary = {}, honor_vary

    def fetch(self, key, headers):
        r = httpx.get(URL, headers=headers)
        if r.status_code == 200:
            self.store[key] = (time.monotonic(), r.text, r.headers["cache-control"])
        return r

    def get(self, lang="en"):
        headers = {"Accept-Language": lang}
        key = (URL, lang) if self.honor_vary else URL
        entry = self.store.get(key)
        if entry:
            stored, body, cc = entry
            age = time.monotonic() - stored
            fresh = directive(cc, "max-age")
            if age < fresh:
                return 200, body, "HIT"
            if age < fresh + directive(cc, "stale-while-revalidate"):
                threading.Thread(target=self.fetch, args=(key, headers)).start()
                return 200, body, "STALE (revalidating)"
            r = self.fetch(key, headers)
            if r.status_code >= 500 and age < fresh + directive(cc, "stale-if-error"):
                return 200, body, "STALE (origin error)"
            return r.status_code, r.text, "MISS"
        r = self.fetch(key, headers)
        return r.status_code, r.text, "MISS"


def timed(cache, lang="en"):
    t = time.perf_counter()
    status, body, how = cache.get(lang)
    return f"{status} {body!r:<11} {how:<22} {(time.perf_counter() - t) * 1000:5.0f} ms"


for cc in ("max-age=1", "max-age=1, stale-while-revalidate=30"):
    STATE.update(cc=cc, down=False)
    c = EdgeCache()
    c.get()
    time.sleep(1.2)
    print(f"A  {cc:<38} first request after expiry: {timed(c)}")

for cc in ("max-age=1", "max-age=1, stale-if-error=60"):
    STATE.update(cc=cc, down=False)
    c = EdgeCache()
    c.get()
    time.sleep(1.2)
    STATE["down"] = True
    print(f"B  {cc:<38} origin 503 after expiry:   {timed(c)}")
STATE["down"] = False

for honor in (False, True):
    STATE.update(cc="max-age=60")
    c = EdgeCache(honor_vary=honor)
    c.get("en")
    print(f"C  {'cache key ignores Vary' if not honor else 'cache key includes Vary':<38} German user gets:          {timed(c, 'de')}")
