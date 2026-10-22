"""P99 latency: measuring it correctly.
A. Averaging two hosts' p99s is not the fleet's p99.
B. Coordinated omission: a service answers in 1 ms but stalls 1 s every 10 s. A closed-loop load generator (send,
   wait, send) records one slow sample per stall; an open-loop one (requests due every 10 ms, latency measured from
   when each was due) records the users who were actually waiting.
C. Sample size: p99 from 50 samples vs 10,000 samples of the same distribution (seeded, 200 repeats).
D. The live adapter's /command/data on localhost: 200 requests, p50 / p99 / max."""
import random
import statistics
import subprocess


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * len(xs) + 0.5)) - 1)]


rng = random.Random(5)
host_a = [rng.gauss(50, 5) for _ in range(9900)]                                   # busy, fast host
host_b = [rng.gauss(50, 5) for _ in range(90)] + [rng.uniform(400, 600) for _ in range(10)]  # small, slow host
avg = (pct(host_a, 99) + pct(host_b, 99)) / 2
print(f"A  p99 host A {pct(host_a, 99):.0f} ms, host B {pct(host_b, 99):.0f} ms; average of the two {avg:.0f} ms; true fleet p99 {pct(host_a + host_b, 99):.0f} ms")


def service_latency(t):                                                            # stall from t=10k s to 10k+1 s
    phase = t % 10.0
    return (1.0 - phase) + 0.001 if phase < 1.0 else 0.001


closed, t = [], 0.0
while t < 60:
    lat = service_latency(t)
    closed.append(lat)
    t += lat + 0.010                                                               # waits for the answer, then 10 ms
opened = []
for i in range(6000):
    due = i * 0.010
    opened.append(service_latency(due))                                            # measured from when it was due
for name, xs in (("closed loop (coordinated omission)", closed), ("open loop (corrected)", opened)):
    print(f"B  {name:<36} samples {len(xs):>5}: p50 {pct(xs, 50) * 1e3:7.1f} ms  p99 {pct(xs, 99) * 1e3:7.1f} ms")

for n in (50, 10_000):
    estimates = [pct([rng.lognormvariate(3, 0.6) for _ in range(n)], 99) for _ in range(200)]
    print(f"C  {n:>6} samples: p99 estimate ranges {min(estimates):6.1f}-{max(estimates):6.1f} ms over 200 repeats (stdev {statistics.stdev(estimates):5.1f})")

times = []
for _ in range(200):
    out = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{time_total}", "http://127.0.0.1:7654/command/data"], capture_output=True, text=True).stdout
    times.append(float(out) * 1e3)
print(f"D  live /command/data, 200 requests: p50 {pct(times, 50):.1f} ms, p99 {pct(times, 99):.1f} ms, max {max(times):.1f} ms")
