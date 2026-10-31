"""Clock skew, with the real adapter (tests/test_adapter.py's fixture).
A. /trigger accepts a signature only within REPLAY_WINDOW (300 s) of the adapter's clock: a sender whose clock is off
   by more than that is locked out entirely.
B. _gate_results' deadline is wall-clock (time.time). A clock step forward (NTP correction, wake from sleep) in the
   middle of the wait ends it at once, though almost no real time has passed. `time` in the module is replaced by a
   stand-in whose wall clock jumps 1,300 s after the first poll; monotonic time is untouched.
C. Ordering by wall-clock timestamps across two machines 2 s apart puts a reply before its request; Lamport clocks
   keep cause before effect."""
import json
import time
import types

from test_adapter import adapter, sign  # noqa: F401  (fixture)


def test_signature_window(adapter):
    module, root, client = adapter
    results = []
    for skew in (0, 299, 301, -301):
        body = json.dumps({"task": f"skew {skew}"}).encode()
        r = client.post("/trigger", content=body, headers=sign(body, timestamp=int(time.time()) + skew))
        results.append(f"{skew:+d} s -> {r.status_code}{' ' + r.json()['detail'] if r.status_code != 202 else ''}")
    print("\nA  sender clock skew: " + "; ".join(results))


def test_wall_clock_deadline(adapter, monkeypatch):
    module, root, client = adapter
    real, polls = time, [0]

    def jumping_time():
        return real.time() + (1300 if polls[0] >= 1 else 0)

    monkeypatch.setattr(module, "time", types.SimpleNamespace(time=jumping_time, sleep=lambda s: None, monotonic=real.monotonic))

    def gh(*cmd, cwd=None):
        polls[0] += 1
        if cmd[1:3] == ("pr", "view"):
            return "abc"
        return json.dumps([{"name": "tests", "bucket": "pending"}])

    monkeypatch.setattr(module, "_run", gh)
    t = real.monotonic()
    try:
        module._gate_results("url", "abc")
        outcome = "returned"
    except RuntimeError as exc:
        outcome = str(exc)
    print(f"B  wall clock steps +1,300 s during the wait: {outcome!r} after {real.monotonic() - t:.3f} s of real time and {polls[0]} gh calls (CHECKS_TIMEOUT {module.CHECKS_TIMEOUT} s)")


def test_lamport():
    skew = {"api": 0.0, "worker": -2.0}                      # the worker's clock runs 2 s behind
    t0 = 1000.0
    events = [("api", "request sent", t0), ("worker", "request received", t0 + 0.01), ("worker", "reply sent", t0 + 0.02), ("api", "reply received", t0 + 0.03)]
    by_wall = sorted(events, key=lambda e: e[2] + skew[e[0]])
    lamport, clock, stamped = {}, {"api": 0, "worker": 0}, []
    last_sent = 0
    for node, what, _ in events:                             # real causal order
        if "received" in what:
            clock[node] = max(clock[node], last_sent) + 1
        else:
            clock[node] += 1
            last_sent = clock[node]
        stamped.append((clock[node], what))
    print(f"C  ordered by wall-clock timestamps: {[e[1] for e in by_wall]}")
    print(f"C  ordered by Lamport clocks:        {[w for _, w in sorted(stamped)]}")
