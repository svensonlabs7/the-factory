"""Rolling deployments, with the real adapter (this working copy's code) under uvicorn on scratch ports and a scratch
FACTORY_ROOT, so the live adapter and its logs are untouched. A client sends GET /health every 10 ms the whole time.
A. Recreate (the factory's deploy today): stop the only instance, start the new one.
B. Rolling over two instances, without a readiness gate: take one out, restart it, put it back as soon as it starts.
C. Rolling over two instances, with a readiness gate: put it back only after its own /health answers."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(sys.argv[1])
ROOT = Path(tempfile.mkdtemp())
shutil.copy(REPO / "HEARTBEAT.template.md", ROOT / "HEARTBEAT.template.md")
ENV = {**os.environ, "FACTORY_ROOT": str(ROOT), "FACTORY_WEBHOOK_SECRET": "scratch"}


def start(port):
    return subprocess.Popen(["uv", "run", "-q", "--python", "3.11", "--with", "fastapi", "--with", "uvicorn", "--",
                             "uvicorn", "factory.intake.webhook_adapter:app", "--port", str(port), "--log-level", "warning"],
                            cwd=REPO, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def healthy(port):
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5).status == 200
    except Exception:
        return False


def wait_ready(port):
    while not healthy(port):
        time.sleep(0.02)


class Balancer:
    """Round-robin over the ports in rotation, no retries: what a plain load balancer does."""
    def __init__(self, ports):
        self.rotation, self.i, self.ok, self.failed, self.stop = list(ports), 0, 0, 0, False

    def loop(self):
        while not self.stop:
            ports = list(self.rotation)
            if ports:
                self.i += 1
                if healthy(ports[self.i % len(ports)]):
                    self.ok += 1
                else:
                    self.failed += 1
            time.sleep(0.01)


def measure(ports, deploy):
    procs = {p: start(p) for p in ports}
    for p in ports:
        wait_ready(p)
    lb = Balancer(ports)
    t = threading.Thread(target=lb.loop)
    t.start()
    time.sleep(0.5)
    began = time.time()
    deploy(lb, procs)
    took = time.time() - began
    time.sleep(0.5)
    lb.stop = True
    t.join()
    for p in procs.values():
        p.terminate()
        p.wait()
    return f"{lb.failed} of {lb.ok + lb.failed} requests failed; deploy took {took:.1f} s"


def recreate(lb, procs):
    (port,) = procs
    procs[port].terminate()
    procs[port].wait()
    procs[port] = start(port)
    wait_ready(port)


def rolling(gate):
    def deploy(lb, procs):
        for port in list(procs):
            lb.rotation.remove(port)          # drain: stop sending it new requests
            time.sleep(0.05)
            procs[port].terminate()
            procs[port].wait()
            procs[port] = start(port)
            if gate:
                wait_ready(port)              # readiness gate
            else:
                time.sleep(0.2)               # "it started", but uvicorn is not listening yet
            lb.rotation.append(port)
            if not gate:
                wait_ready(port)              # (only so the next step does not overlap)
    return deploy


print("A  recreate, 1 instance:            ", measure([18701], recreate))
print("B  rolling, 2 instances, no gate:   ", measure([18711, 18712], rolling(gate=False)))
print("C  rolling, 2 instances, readiness: ", measure([18721, 18722], rolling(gate=True)))
shutil.rmtree(ROOT)
