"""Optimistic locking.
A. Two editors read version 1 of a record and both save. Without a version check, the second silently erases the first
   (lost update). With If-Match-style checking, the second save is refused (412) and must re-read and re-apply.
B. Real git in scratch repos: a non-forced push is a compare-and-swap on the remote ref. The factory pushes this way,
   so if a human commits to a factory branch mid-round, the adapter's stale push is rejected instead of erasing it.
   --force erases the human's commit; --force-with-lease=<ref>:<expected sha> refuses when the expectation is stale."""
import os
import subprocess
import tempfile

store = {"doc": {"version": 1, "text": "base"}}


def save(new_text, read_version, check):
    current = store["doc"]
    if check and current["version"] != read_version:
        return "412 Precondition Failed (re-read and re-apply)"
    store["doc"] = {"version": current["version"] + 1, "text": new_text}
    return "saved"


for check in (False, True):
    store["doc"] = {"version": 1, "text": "base"}
    v = store["doc"]["version"]                       # both editors read version 1
    r1 = save("base + Alice's paragraph", v, check)
    r2 = save("base + Bob's paragraph", v, check)    # Bob never saw Alice's change
    print(f"A  {'with' if check else 'without'} version check: Alice {r1}; Bob {r2}; final text: {store['doc']['text']!r}")


def git(cwd, *a, check=True):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(r.stderr)
    return r


tmp = tempfile.mkdtemp()
origin, human, adapter = (os.path.join(tmp, d) for d in ("origin.git", "human", "adapter"))
git(tmp, "init", "-q", "--bare", "-b", "main", origin)
git(tmp, "clone", "-q", origin, human)
open(os.path.join(human, "f"), "w").write("round 1")
git(human, "add", "-A"); git(human, "commit", "-qm", "factory round 1"); git(human, "push", "-q", "origin", "HEAD:refs/heads/factory/x")
git(tmp, "clone", "-q", "-b", "factory/x", origin, adapter)        # the next fix round starts from this head
base = git(adapter, "rev-parse", "HEAD").stdout.strip()

open(os.path.join(human, "f"), "w").write("human hotfix")           # meanwhile a human pushes to the branch
git(human, "commit", "-qam", "human hotfix"); git(human, "push", "-q", "origin", "HEAD:refs/heads/factory/x")
human_sha = git(human, "rev-parse", "HEAD").stdout.strip()

open(os.path.join(adapter, "f"), "w").write("round 2")
git(adapter, "commit", "-qam", "factory round 2")
head = git(adapter, "rev-parse", "HEAD").stdout.strip()
r = git(adapter, "push", "origin", f"{head}:refs/heads/factory/x", check=False)
print(f"\nB  adapter's plain push (as _push does): exit {r.returncode}: {[l for l in r.stderr.splitlines() if 'rejected' in l][0].strip()}")
r = git(adapter, "push", f"--force-with-lease=factory/x:{base}", "origin", f"{head}:refs/heads/factory/x", check=False)
print(f"B  --force-with-lease expecting the old head: exit {r.returncode}: {[l for l in r.stderr.splitlines() if 'rejected' in l][0].strip()}")
git(adapter, "push", "--force", "origin", f"{head}:refs/heads/factory/x")
remote = git(origin, "rev-parse", "factory/x").stdout.strip()
reachable = git(origin, "merge-base", "--is-ancestor", human_sha, "factory/x", check=False).returncode == 0
print(f"B  --force: remote now at the adapter's commit = {remote == head}; human's hotfix still on the branch = {reachable}")
