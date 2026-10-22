"""Leader election.
A. Raft-style elections in 5 nodes, 10 ms vote round trip: every node that times out within one round trip of the
   first becomes a candidate too, votes split, and the term is retried. Fixed timeouts vs randomized (150-300 ms).
B. Single-host leader election with an OS lock (fcntl.flock on a file), real processes: the lease is the process's
   life, so a killed leader's lock is released at once, while a frozen (SIGSTOP) leader keeps it."""
import os
import random
import signal
import subprocess
import sys
import tempfile
import time

rng = random.Random(9)


def rounds_to_leader(randomized, nodes=5, rtt=0.010, limit=50):
    for r in range(1, limit + 1):
        timeouts = [rng.uniform(0.150, 0.300) if randomized else 0.150 for _ in range(nodes)]
        first = min(timeouts)
        candidates = [t for t in timeouts if t - first < rtt]   # these start before the first request reaches them
        if len(candidates) == 1:                                 # one candidate collects a majority
            return r
    return None


for randomized in (False, True):
    results = [rounds_to_leader(randomized) for _ in range(1000)]
    elected = [r for r in results if r]
    label = "randomized 150-300 ms" if randomized else "fixed 150 ms"
    avg = sum(elected) / len(elected) if elected else float("nan")
    print(f"A  {label:<22}: leader elected in {len(elected)}/1000 trials; mean rounds {avg:.2f}")

LOCK = tempfile.mktemp()
LEADER = f"""
import fcntl, sys, time
f = open({LOCK!r}, "w")
try:
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("follower", flush=True); sys.exit(0)
print("leader", flush=True)
time.sleep(3600)
"""


def contender():
    return subprocess.run([sys.executable, "-c", LEADER], capture_output=True, text=True, timeout=5).stdout.strip()


a = subprocess.Popen([sys.executable, "-c", LEADER], stdout=subprocess.PIPE, text=True)
print(f"B  process A: {a.stdout.readline().strip()}; process B now: {contender()}")
os.kill(a.pid, signal.SIGSTOP)
time.sleep(0.5)
print(f"B  A frozen (SIGSTOP) for 0.5 s; B tries: {contender()}  (no second leader while A could still wake up)")
os.kill(a.pid, signal.SIGKILL)
a.wait()
t = time.perf_counter()
b = subprocess.Popen([sys.executable, "-c", LEADER], stdout=subprocess.PIPE, text=True)
role = b.stdout.readline().strip()
print(f"B  A killed (SIGKILL); B tries: {role} after {(time.perf_counter() - t) * 1000:.0f} ms, no timeout to wait out")
b.kill()
