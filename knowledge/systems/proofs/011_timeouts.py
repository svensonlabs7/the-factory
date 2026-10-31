"""Timeouts: show each failure, then its fix.
A. A remote call with no timeout waits as long as the server stalls; a timeout bounds it.
B. subprocess.run(timeout=) kills only the direct child; a grandchild survives. A process group fixes it."""
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.request

# A: a server that accepts the connection and never answers (a hung dependency).
srv = socket.socket()
srv.bind(("127.0.0.1", 0))
srv.listen()
port = srv.getsockname()[1]
held = []
threading.Thread(target=lambda: [held.append(srv.accept()) for _ in range(2)], daemon=True).start()
url = f"http://127.0.0.1:{port}/"


def call(timeout):
    t = time.time()
    try:
        urllib.request.urlopen(url, timeout=timeout) if timeout else urllib.request.urlopen(url)
        return f"returned after {time.time() - t:.1f}s"
    except Exception as exc:
        return f"{type(exc).__name__} after {time.time() - t:.1f}s"


# No timeout: run it in a thread and look at it after 5s; it is still waiting, and would wait forever.
t = threading.Thread(target=lambda: print("A-fail finished:", call(None)), daemon=True)
t.start()
t.join(5)
print(f"A-fail no timeout: still waiting after 5s = {t.is_alive()}")
print(f"A-fix  timeout=1: {call(1)}")

# B: the child is a shell that starts a long grandchild, like `uv run` starting run_agent.py.
cmd = ["sh", "-c", "sleep 300 & wait"]


def grandchildren_alive():
    return subprocess.run(["pgrep", "-f", "^sleep 300$"], capture_output=True, text=True).stdout.split()


try:
    subprocess.run(cmd, timeout=1)
except subprocess.TimeoutExpired:
    pass
left = grandchildren_alive()
print(f"B-fail run(timeout=1): grandchild still running = {bool(left)} {left}")
for pid in left:
    os.kill(int(pid), signal.SIGKILL)

p = subprocess.Popen(cmd, start_new_session=True)
try:
    p.wait(timeout=1)
except subprocess.TimeoutExpired:
    os.killpg(p.pid, signal.SIGTERM)
    p.wait()
time.sleep(0.2)
print(f"B-fix  new session + killpg: grandchild still running = {bool(grandchildren_alive())}")

# C: urllib's timeout is per socket operation, not a total deadline. A server that drips one byte every
# 0.5s keeps a timeout=1 call alive far past 1s. The fix is a total deadline around the whole call.
drip = socket.socket()
drip.bind(("127.0.0.1", 0))
drip.listen()


def serve_drip():
    conn, _ = drip.accept()
    conn.recv(1024)
    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\n\r\n")
    for _ in range(8):
        time.sleep(0.5)
        conn.sendall(b"x")
    conn.close()


threading.Thread(target=serve_drip, daemon=True).start()
t = time.time()
body = urllib.request.urlopen(f"http://127.0.0.1:{drip.getsockname()[1]}/", timeout=1).read()
print(f"C-fail timeout=1 per operation: finished after {time.time() - t:.1f}s, no timeout raised ({len(body)} bytes)")

drip2 = socket.socket()
drip2.bind(("127.0.0.1", 0))
drip2.listen()
drip = drip2
threading.Thread(target=serve_drip, daemon=True).start()
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
t = time.time()
try:
    ThreadPoolExecutor(1).submit(lambda: urllib.request.urlopen(f"http://127.0.0.1:{drip2.getsockname()[1]}/", timeout=1).read()).result(timeout=1.5)
except FutureTimeout:
    print(f"C-fix  total deadline 1.5s: gave up after {time.time() - t:.1f}s")
