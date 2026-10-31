"""Liveness and readiness probes.
A. The real adapter (fixture): block the event loop that serves requests. The alive_at thread keeps stamping
   HEARTBEAT while /health cannot answer: alive_at proves the process lives, not that it serves.
B. Simulation of two probe mistakes, in seconds of simulated time over 10 minutes:
   1. a liveness probe that checks a shared dependency restarts healthy pods all through a dependency outage;
   2. a liveness probe whose initial delay is shorter than startup kills the app before it ever starts.
   The fixes: dependency checks belong in readiness; a startup probe holds liveness off until started."""
import threading
import time

from test_adapter import adapter  # noqa: F401  (fixture)


def test_alive_stamp_vs_serving(adapter, monkeypatch):
    module, root, _ = adapter
    monkeypatch.setattr(module, "ALIVE_INTERVAL", 0.2)
    stamps = []
    real_set = module._set_heartbeat

    def recording_set(**fields):
        if "alive_at" in fields:
            stamps.append(time.time())
        real_set(**fields)
    monkeypatch.setattr(module, "_set_heartbeat", recording_set)

    @module.app.get("/wedge")
    async def wedge():  # blocks the event loop, as a deadlock or a sync call inside async code would
        time.sleep(3)
        return {}

    from fastapi.testclient import TestClient
    with TestClient(module.app) as client:  # one event loop for every request, and the lifespan's alive thread runs
        threading.Thread(target=lambda: client.get("/wedge"), daemon=True).start()
        time.sleep(0.3)
        t = time.time()
        client.get("/health")
        health_took = time.time() - t
    during = [s for s in stamps if t <= s <= t + health_took]
    print(f"\nA  /health took {health_took:.1f} s while the loop was blocked; alive_at was stamped {len(during)} times meanwhile")


def simulate(liveness_checks_dependency, initial_delay, startup_time, startup_probe):
    """One pod. Dependency down from t=120 to t=300. Probes every 10 s, 3 failures to act."""
    t, started_at, restarts, served, fails = 0, 0, 0, 0, 0
    while t < 600:
        dep_up = not (120 <= t < 300)
        up = t - started_at >= startup_time
        if up and dep_up:
            served += 10
        probing = (t - started_at >= initial_delay) and (up or not startup_probe)
        if probing:
            ok = up and (dep_up or not liveness_checks_dependency)
            fails = 0 if ok else fails + 1
            if fails >= 3:
                restarts, started_at, fails = restarts + 1, t, 0
        t += 10
    return restarts, served


def test_probe_mistakes():
    print("\nB  case                                          restarts  seconds served of 420 possible")
    for label, args in (
        ("liveness checks the dependency", (True, 30, 20, False)),
        ("liveness checks only the process", (False, 30, 20, False)),
        ("startup 90 s, liveness delay 30 s", (False, 30, 90, False)),
        ("startup 90 s, startup probe", (False, 30, 90, True)),
    ):
        restarts, served = simulate(*args)
        print(f"B  {label:<44}{restarts:>8}{served:>10}")
