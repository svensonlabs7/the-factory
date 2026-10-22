"""Infrastructure as Code: the infrastructure is defined in version-controlled files and applied by a tool that
makes reality match the files. The two properties that make it IaC rather than a shell script are IDEMPOTENCE
(applying the same definition twice is safe and a no-op the second time) and DRIFT RECONCILIATION (if reality
drifts from the files, the next apply corrects it).

A. Imperative `create` vs declarative `apply`, run twice:
   - imperative create: each run adds the resource -> second run duplicates (or errors). Not idempotent.
   - declarative apply: reconciles current -> desired -> second run reports 0 changes. Idempotent.
B. Drift: something changes a resource out of band; the next `apply` detects and corrects it.
Pure Python model of a 'cloud'; no network."""


def imperative_create(cloud, name, config):
    cloud.append({"name": name, "config": config})   # blindly creates another one
    return f"created {name} (now {sum(r['name'] == name for r in cloud)} of it)"


def apply(cloud, desired):
    """Declarative: make the cloud match `desired` (name -> config). Returns (to_add, to_change, unchanged)."""
    by_name = {r["name"]: r for r in cloud}
    add = [n for n in desired if n not in by_name]
    change = [n for n in desired if n in by_name and by_name[n]["config"] != desired[n]]
    unchanged = [n for n in desired if n in by_name and by_name[n]["config"] == desired[n]]
    for n in add:
        cloud.append({"name": n, "config": desired[n]})
    for n in change:
        next(r for r in cloud if r["name"] == n)["config"] = desired[n]
    return add, change, unchanged


print("A  imperative create, run twice:")
cloud = []
print("   ", imperative_create(cloud, "tunnel", {"port": 7654}))
print("   ", imperative_create(cloud, "tunnel", {"port": 7654}), "<- duplicate; not idempotent")

print("A  declarative apply, run twice:")
cloud, desired = [], {"tunnel": {"port": 7654}, "egress": {"ip": "172.30.0.2"}}
add, change, _ = apply(cloud, desired)
print(f"    run 1: +{len(add)} add, ~{len(change)} change  {add}")
add, change, unchanged = apply(cloud, desired)
print(f"    run 2: +{len(add)} add, ~{len(change)} change, {len(unchanged)} unchanged <- idempotent no-op")

print("B  drift: an out-of-band edit changes the tunnel's port; next apply reconciles:")
next(r for r in cloud if r["name"] == "tunnel")["config"] = {"port": 9999}  # someone edited the live copy
add, change, unchanged = apply(cloud, desired)
tunnel_now = next(r for r in cloud if r["name"] == "tunnel")["config"]
print(f"    apply: ~{len(change)} change {change} -> tunnel back to {tunnel_now} (drift corrected)")
