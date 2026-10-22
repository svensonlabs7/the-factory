"""Vertical scaling: more cores help only the parallel part (Amdahl), and only the cores the workload can see.
Workload: 8 equal CPU-bound chunks run across N worker processes, plus a serial step sized so it is 20% of the
one-worker time. Prints measured speedup vs Amdahl's prediction 1 / (s + (1 - s) / N), and the CPUs visible."""
import os
import sys
import time
from multiprocessing import Pool


def burn(n):
    x = 0
    for i in range(n):
        x += i * i
    return x


CHUNK = 3_000_000


def run(workers, serial_iters):
    t = time.perf_counter()
    burn(serial_iters)                                   # the serial part
    with Pool(workers) as p:
        p.map(burn, [CHUNK] * 8)                         # the parallel part
    return time.perf_counter() - t


if __name__ == "__main__":
    where = sys.argv[1] if len(sys.argv) > 1 else "host"
    t0 = time.perf_counter()
    burn(CHUNK)
    one_chunk = time.perf_counter() - t0
    serial_iters = int(CHUNK * 8 * 0.25)                 # serial = 20% of (serial + 8 chunks) on one worker
    base = run(1, serial_iters)
    s = 0.2
    print(f"{where}: {os.cpu_count()} CPUs visible; 1 worker {base:5.2f} s")
    for n in (2, 4, 8):
        speed = base / run(n, serial_iters)
        print(f"{where}: {n} workers -> speedup {speed:4.2f}x (Amdahl with 20% serial: {1 / (s + (1 - s) / n):4.2f}x)")
