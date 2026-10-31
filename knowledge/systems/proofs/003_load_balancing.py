"""Load balancing: the dispatch algorithm decides the tail, not the average.

Discrete-event sim: requests arrive at a steady rate to 3 identical backends, each serving one request at a
time with a FIFO queue. Service times are skewed -- most cheap, a few very expensive (a realistic mix).
Compare dispatch policies:
- round-robin: rotate regardless of how busy each backend is. An expensive request parks on a backend and the
  rotation keeps piling new requests behind it -> head-of-line blocking on that queue.
- least-connections: send each request to the backend with the fewest in-flight requests -> work routes around
  a backend stuck on an expensive request.
- p2c (power of two choices): pick two backends at random, send to the less busy -> nearly least-connections
  with O(1) state, the standard result (Mitzenmacher).
Same arrivals and same service times across policies, so only the dispatch differs. Deterministic seed."""
import random
import statistics

random.seed(11)
N = 3
ARRIVALS = 3000
RATE = 2.1  # ~0.66 utilization across 3 backends (mean service ~= 0.95): all policies stable, so it is a tail test


def service_time():
    # 90% cheap (~0.5), 10% expensive (~5.0): mean ~= 0.95, heavy tail.
    return random.expovariate(1 / 5.0) if random.random() < 0.10 else random.expovariate(1 / 0.5)


# Pre-generate identical arrivals and service times for every policy.
t, arrivals = 0.0, []
for _ in range(ARRIVALS):
    t += random.expovariate(RATE)
    arrivals.append((t, service_time()))


# A backend is "busy" while now < free_at, and backlog is the queued work ahead of a new arrival.
def simulate2(policy):
    free_at = [0.0] * N
    waits, qdepth_peak = [], 0
    rr = 0
    for arr, svc in arrivals:
        busy = [1 if free_at[b] > arr else 0 for b in range(N)]  # 1 if still working at arrival
        backlog = [max(0.0, free_at[b] - arr) for b in range(N)]  # time of queued work ahead
        if policy == "round-robin":
            b = rr; rr = (rr + 1) % N
        elif policy == "least-conn":
            b = min(range(N), key=lambda i: (busy[i], backlog[i]))
        else:  # p2c
            i, j = random.sample(range(N), 2)
            b = i if backlog[i] <= backlog[j] else j
        start = max(arr, free_at[b])
        free_at[b] = start + svc
        waits.append(start - arr)
    return waits


random.seed(11)  # p2c uses randomness; fix it so the run is reproducible
for policy in ("round-robin", "least-conn", "p2c"):
    w = simulate2(policy)
    w_sorted = sorted(w)
    p99 = w_sorted[int(0.99 * len(w))]
    print(f"{policy:12s}: mean wait {statistics.mean(w):.3f}  p99 wait {p99:6.3f}  max wait {max(w):6.3f}")
