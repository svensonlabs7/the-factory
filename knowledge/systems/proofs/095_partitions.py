"""Network partitions: the ambiguous outcome of a write.
A. Real sockets: client -> proxy -> a tiny "GitHub" HTTP server. The proxy forwards POST /pulls, the server creates
   the PR and answers, and the partition eats the answer (the proxy resets the client instead of relaying it).
   Then: the naive client's retry, and an idempotent client that looks the PR up by its branch after an unclear failure.
B. The real adapter (tests/test_adapter.py's fixture): `gh pr create` creates the PR but its response is lost."""
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from test_adapter import adapter, trigger, wait_done  # noqa: F401  (fixture)

PULLS = {}


class GitHub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        head = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["head"]
        if head in PULLS:
            return self._send(422, {"message": f"A pull request already exists for {head}."})
        PULLS[head] = f"https://github.example/pull/{len(PULLS) + 1}"
        self._send(201, {"html_url": PULLS[head]})

    def do_GET(self):
        head = self.path.split("head=")[-1]
        self._send(200, [{"html_url": PULLS[head]}] if head in PULLS else [])


def proxy(listen, upstream, partition):
    """Relays one connection at a time; while `partition` is set it relays requests but drops the replies."""
    while True:
        client, _ = listen.accept()
        up = socket.create_connection(upstream)
        request = client.recv(65536)
        up.sendall(request)
        reply = b""
        while chunk := up.recv(65536):   # the server closes after one response (HTTP/1.0)
            reply += chunk
        if partition.is_set() and request.startswith(b"POST"):
            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")
            client.close()                     # the reply never arrives: the client sees a reset
        else:
            client.sendall(reply)
            client.close()
        up.close()


def test_ambiguous_write():
    server = ThreadingHTTPServer(("127.0.0.1", 0), GitHub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    listen = socket.create_server(("127.0.0.1", 0))
    partition = threading.Event()
    threading.Thread(target=proxy, args=(listen, server.server_address, partition), daemon=True).start()
    base = f"http://127.0.0.1:{listen.getsockname()[1]}"

    partition.set()
    try:
        httpx.post(f"{base}/pulls", json={"head": "factory/abc"}, timeout=2)
        first = "ok"
    except httpx.HTTPError as exc:
        first = type(exc).__name__
    partition.clear()
    print(f"\nA  create PR during the partition: client saw {first}; server has {len(PULLS)} PR(s)")
    retry = httpx.post(f"{base}/pulls", json={"head": "factory/abc"})
    print(f"A  naive retry: {retry.status_code} {retry.json()['message']}")
    found = httpx.get(f"{base}/pulls?head=factory/abc").json()
    print(f"A  idempotent client, look up by branch after the unclear failure: {found[0]['html_url']}")


def test_adapter_lost_response(adapter, monkeypatch):
    module, root, client = adapter
    created, real = [], module._run

    def run(*cmd, cwd=module.FACTORY_ROOT):
        if cmd[1:3] == ("pr", "create"):
            created.append(real(*cmd, cwd=cwd))   # GitHub creates the PR...
            raise RuntimeError("gh pr create: read tcp: connection reset by peer")  # ...and the answer is lost
        return real(*cmd, cwd=cwd)

    monkeypatch.setattr(module, "_run", run)
    run_id = trigger(client).json()["run_id"]
    done = wait_done(client, run_id)
    print(f"B  run {run_id}: status {done['status']!r}, pr_url recorded {done.get('pr_url')!r}; PRs that exist on GitHub: {created}")
