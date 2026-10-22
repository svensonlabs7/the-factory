"""Autoscaling, simulated with Kubernetes' HPA rule: desired = ceil(current * load_per_replica / target), skipped
within a 0.1 tolerance, evaluated every 15 s. Each replica serves 100 req/s at 100% CPU; target 60%. New replicas
take 60 s to become ready. Traffic: noisy around 300 req/s, then a step to 900 req/s at t=600 s (seeded).
A. No downscale stabilization: replica count flaps with the noise.
B. 300 s downscale stabilization (the HPA default): scale-down uses the highest recommendation of the last 300 s.
C. The step: requests above ready capacity while new replicas warm up."""
import math
import random


def run(stabilize, seconds=1200):
    rng = random.Random(8)
    replicas, ready_at, history, changes, dropped = 5, [], [], 0, 0.0
    ready = 5
    for t in range(0, seconds, 15):
        load = (900 if t >= 600 else 300) * rng.uniform(0.75, 1.25)
        ready = replicas - sum(1 for r in ready_at if r > t)
        dropped += max(0.0, load - ready * 100) * 15
        util = load / (ready * 100) * 100
        desired = replicas if abs(util / 60 - 1) <= 0.1 else math.ceil(ready * util / 60)
        history.append((t, desired))
        if stabilize and desired < replicas:
            desired = max(d for (ht, d) in history if ht > t - 300)
        if desired != replicas:
            changes += 1
            if desired > replicas:
                ready_at += [t + 60] * (desired - replicas)
            replicas = desired
    return changes, replicas, dropped


for name, stab in (("no stabilization", False), ("300 s downscale stabilization", True)):
    changes, final, dropped = run(stab)
    print(f"{'A' if not stab else 'B'}  {name:<30}: {changes:>3} replica-count changes in 20 min; final {final} replicas")
_, _, dropped = run(True)
print(f"C  step 300 -> 900 req/s with 60 s replica warm-up: {dropped:,.0f} requests above ready capacity during the scale-up")
