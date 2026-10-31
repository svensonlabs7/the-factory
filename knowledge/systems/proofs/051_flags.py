"""Feature flags. Knight Capital's failure mode (SEC Release 34-70694), reduced to its parts:
eight servers, the new code reaches seven, and the new feature is switched on with a flag that used to switch on old,
dead code that was never deleted. The stale server runs the dead path.
Fixes: a fresh flag name (unknown flags default off), deleting the dead code, and checking the fleet's version before
flipping the flag."""

DEAD_CODE_ORDERS = 1000  # Power Peg: a child-order loop whose stop condition had been moved away


def server(version, flags, has_dead_code=True):
    def handle(order):
        if version == "new" and flags.get("rlp", flags.get("power_peg")):
            return 1  # RLP: one correct order
        if version == "old" and flags.get("power_peg") and has_dead_code:
            return DEAD_CODE_ORDERS  # the old meaning of the flag, still callable
        return 1
    return handle


def run(fleet_versions, flags, has_dead_code=True, preflight=False):
    if preflight and set(fleet_versions) != {"new"}:
        return "flag flip refused: fleet versions " + str(sorted(set(fleet_versions)))
    fleet = [server(v, flags, has_dead_code) for v in fleet_versions]
    sent = sum(fleet[i % len(fleet)](i) for i in range(212))
    return f"212 parent orders -> {sent:,} child orders sent"


fleet = ["new"] * 7 + ["old"]  # one technician missed one server
print("A  repurposed flag 'power_peg', 7/8 deployed:  ", run(fleet, {"power_peg": True}))
print("A  same, every server deployed:                ", run(["new"] * 8, {"power_peg": True}))
print("B  fix 1, fresh flag 'rlp' (old code ignores it):", run(fleet, {"rlp": True}))
print("B  fix 2, dead code deleted, flag reused:       ", run(fleet, {"power_peg": True}, has_dead_code=False))
print("B  fix 3, fleet version checked before the flip:", run(fleet, {"rlp": True}, preflight=True))
