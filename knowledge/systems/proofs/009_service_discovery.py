"""Service discovery: a registry maps a service name to the set of live instance addresses, and clients look
it up instead of hard-coding addresses. The hard part is not registration -- it is DEREGISTRATION: an instance
that dies must leave the registry, or clients keep routing to a ghost.

Model a registry of instances for one service. Each instance heartbeats every HB ticks. At t=20, instance B
crashes and stops heartbeating. Compare two registries:
- no-expiry : entries live until explicitly removed -> B stays advertised forever -> clients keep picking it.
- ttl-expiry: an entry is dropped if its last heartbeat is older than TTL (Consul/etcd lease, Eureka renewal) ->
  B ages out TTL ticks after it died, and lookups return only live instances.
A client resolves the service each tick and "calls" a random listed instance; a call to a dead instance fails.
Deterministic virtual clock and seed; no network."""
import random

random.seed(5)
HB, TTL, END, CRASH = 5, 12, 60, 20
INSTANCES = ["A", "B", "C"]


def run(ttl_expiry):
    last_hb = {name: 0 for name in INSTANCES}   # registry: name -> last heartbeat time (0 = registered at start)
    failures = 0
    ghost_listed_after_death = 0
    for t in range(END):
        # Instances heartbeat, except B after it crashes.
        for name in INSTANCES:
            if name == "B" and t >= CRASH:
                continue
            if t % HB == 0:
                last_hb[name] = t
        # The registry's current view.
        if ttl_expiry:
            listed = [n for n, hb in last_hb.items() if t - hb <= TTL]
        else:
            listed = list(last_hb)                # never forgets
        # A client resolves and calls one listed instance.
        if listed:
            target = random.choice(listed)
            alive = not (target == "B" and t >= CRASH)
            if not alive:
                failures += 1
        if t >= CRASH and "B" in listed:
            ghost_listed_after_death += 1
    return failures, ghost_listed_after_death


for ttl in (False, True):
    f, ghost = run(ttl)
    label = "ttl-expiry " if ttl else "no-expiry  "
    print(f"{label}: B advertised for {ghost:2d} ticks after it died at t={CRASH}; "
          f"{f:2d} client calls hit the dead instance")
print(f"(B's last heartbeat was t=15, so with TTL={TTL} it ages out at t=28 — 8 ticks after it died; "
      f"no-expiry never removes it: {END - CRASH} ticks of ghost to the end of the run)")
