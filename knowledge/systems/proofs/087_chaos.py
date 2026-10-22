"""Chaos engineering: deliberately inject real-world faults to verify that the resilience you BELIEVE you have
is actually there. The method (principlesofchaos.org): state a steady-state hypothesis (a measurable 'healthy'
metric), inject a fault, and check the hypothesis still holds -- while keeping the BLAST RADIUS small (run on a
slice of traffic, be ready to abort) so the experiment itself does not cause the incident.

Model a service that depends on D. Steady state: success rate >= 99%. Inject 'D is down' and measure, with and
without a fallback (cache/default). The experiment reveals whether the assumed resilience is real.
Also show blast-radius control: apply the fault to only 5% of traffic so worst-case impact is bounded.
Deterministic; no randomness, no network."""
N = 1000
STEADY_STATE = 0.99          # hypothesis: at least 99% of requests succeed


def run(has_fallback, fault_fraction):
    ok = 0
    for i in range(N):
        in_experiment = (i % 100) < (fault_fraction * 100)   # this request is in the fault slice
        d_down = in_experiment                                # inside the slice, D is down
        if not d_down:
            ok += 1                                           # D up -> success
        elif has_fallback:
            ok += 1                                           # D down but fallback serves a cached/default answer
        # else: D down, no fallback -> this request fails
    return ok / N


print("Inject 'dependency D is down' on 100% of traffic (full experiment):")
for has_fallback in (False, True):
    rate = run(has_fallback, fault_fraction=1.0)
    verdict = "hypothesis HOLDS (resilience real)" if rate >= STEADY_STATE else "hypothesis VIOLATED (weakness found)"
    print(f"   fallback={str(has_fallback):5}: success {rate:5.0%} -> {verdict}")

print("\nBlast-radius control: no fallback, but inject on only 5% of traffic:")
rate = run(has_fallback=False, fault_fraction=0.05)
print(f"   success {rate:5.0%} -> worst-case impact capped at 5%; the experiment is abortable before it becomes an incident")
