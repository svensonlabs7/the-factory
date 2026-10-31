"""IAM (identity and access management) is about who may do what. The foundational defensive principle is LEAST
PRIVILEGE: give each identity only the permissions its job needs, so that if the identity is compromised, the
damage (blast radius) is limited to those permissions. The companion is PRIVILEGE SEPARATION: give each workload
its own narrow identity rather than one shared powerful one.

Model: a set of possible actions on the system. A workload needs exactly one of them. Compare what a compromise
of that workload's credential can do when the credential is least-privilege vs over-broad ('admin'). Blast
radius = the actions the stolen credential authorises. Pure defensive illustration; no network, no secrets."""

ALL_ACTIONS = {
    "push factory/* branches", "push main", "delete repo", "read secrets",
    "merge PRs", "change branch protection", "rotate tokens",
}
WORKLOAD_NEEDS = {"push factory/* branches"}   # the only action the build workload legitimately performs


def blast_radius(granted):
    """If this credential is stolen, what can the attacker do? = the actions it was granted."""
    return granted & ALL_ACTIONS


least_privilege = WORKLOAD_NEEDS                 # granted only what the job needs
over_broad = set(ALL_ACTIONS)                    # an 'admin' token reused for convenience

for label, grant in (("least-privilege token", least_privilege), ("over-broad (admin) token", over_broad)):
    radius = blast_radius(grant)
    does_job = WORKLOAD_NEEDS <= grant
    print(f"{label:26s}: does its job={does_job}; if stolen, attacker can do {len(radius)}/{len(ALL_ACTIONS)} actions")
    if radius - WORKLOAD_NEEDS:
        print(f"    beyond its job: {sorted(radius - WORKLOAD_NEEDS)}")

print("\nBoth tokens do the job equally; only the blast radius differs. Least privilege costs nothing in function "
      "and caps the damage of a compromise -- which is why the factory's sandbox holds NO push credential at all.")
