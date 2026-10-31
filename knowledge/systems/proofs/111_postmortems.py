"""A postmortem's value is not the write-up; it is the tracked ACTION ITEM that removes a cause so the incident
cannot recur. Blameless analysis exists to make that honest: if people fear blame they hide the real cause, so
few causes are actually removed and the same latent fault fires again. The payoff compounds over time.

Model: a system has LATENT_CAUSES latent faults. Left in place, each fault recurs as an incident every RECUR
periods over a horizon. A postmortem with a completed action item removes a fault after its FIRST incident, so
it never fires again. Compare removal rates:
- no postmortem (0%)  : no fault removed -> each recurs for the whole horizon.
- blame culture (~30%): only the few faults whose true cause was admitted are removed; the rest keep recurring.
- blameless (100%)    : every incident's root cause is removed -> each fault fires exactly once, then never.
Deterministic; counts cumulative incidents over the horizon. No external calls."""
HORIZON = 20
RECUR = 5
LATENT_CAUSES = 8


def simulate(remove_fraction):
    removed_causes = int(round(remove_fraction * LATENT_CAUSES))  # which causes get a completed action item
    cumulative = 0
    for cause in range(LATENT_CAUSES):
        removed = cause < removed_causes
        for t in range(0, HORIZON + 1, RECUR):   # this fault's recurrence schedule
            cumulative += 1                        # it fires
            if removed:
                break                              # action item removed the root cause after the first time
    return cumulative


for label, frac in (("no postmortem (remove 0%)", 0.0),
                    ("blame culture (remove ~30%)", 0.30),
                    ("blameless + actions (remove 100%)", 1.0)):
    total = simulate(frac)
    print(f"{label:36s}: {total:2d} cumulative incidents over {HORIZON} periods")
print(f"\nSame {LATENT_CAUSES} latent faults, same horizon; only the share of incidents whose root cause is "
      f"actually removed differs. Blameless postmortems fire each fault once ({LATENT_CAUSES}); with no "
      f"postmortem every fault keeps recurring.")
