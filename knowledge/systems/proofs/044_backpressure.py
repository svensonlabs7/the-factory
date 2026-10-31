"""Backpressure.
A. Simulated time: 12 jobs/s arrive for 60 s, then 8/s for 120 s; one consumer does 10/s.
   Unbounded queue vs bounded queue that rejects (load shedding) vs bounded queue that blocks the producer.
B. A real OS pipe: the kernel's pipe buffer is backpressure. A parent that waits without reading deadlocks."""
import subprocess
import sys
import time
from collections import deque


def simulate(mode, bound=20):
    q, t, waits, rejected, sent, peak = deque(), 0.0, [], 0, 0, 0
    next_service = 0.0
    arrivals = [i / 12 for i in range(12 * 60)] + [60 + i / 8 for i in range(8 * 120)]
    i = 0
    producer_free_at = 0.0
    while i < len(arrivals) or q:
        arrive = max(arrivals[i], producer_free_at) if i < len(arrivals) else float("inf")
        if q and next_service <= arrive:  # serve one job
            t = max(next_service, q[0])
            waits.append((t - q.popleft(), t))
            next_service = t + 0.1
            continue
        t = arrive
        if len(q) < bound or mode == "unbounded":
            q.append(t)
            sent += 1
        elif mode == "reject":
            rejected += 1
        else:  # block: the producer waits until the consumer frees a slot
            producer_free_at = next_service
            continue
        peak = max(peak, len(q))
        i += 1
    overload = [w for w, at in waits if at < 60]
    drained = max(at for w, at in waits)
    return peak, max(overload), sorted(w for w, _ in waits)[int(len(waits) * 0.99)], rejected, drained


print("A  12/s for 60 s, then 8/s for 120 s; consumer 10/s")
print(f"A  {'queue':<22}{'peak depth':>11}{'max wait':>10}{'p99 wait':>10}{'rejected':>10}{'last job done':>15}")
for mode in ("unbounded", "reject", "block"):
    peak, worst, p99, rejected, drained = simulate(mode)
    label = {"unbounded": "unbounded", "reject": "bounded 20, reject", "block": "bounded 20, block"}[mode]
    print(f"A  {label:<22}{peak:>11}{worst:>9.1f}s{p99:>9.1f}s{rejected:>10}{drained:>14.0f}s")

child = [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1_000_000)"]
p = subprocess.Popen(child, stdout=subprocess.PIPE)
t = time.time()
try:
    p.wait(timeout=3)
    print("B  wait() without reading: finished")
except subprocess.TimeoutExpired:
    print(f"B  wait() without reading a 1 MB stdout pipe: still blocked after {time.time() - t:.0f}s (child stuck on a full pipe)")
    p.kill()
    p.wait()
out, _ = subprocess.Popen(child, stdout=subprocess.PIPE).communicate(timeout=10)
print(f"B  communicate() reads while waiting: got {len(out):,} bytes")
