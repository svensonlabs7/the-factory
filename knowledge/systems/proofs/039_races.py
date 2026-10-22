"""Race conditions.
A. Lost update: 8 threads each do read-modify-write on a shared counter file 50 times. Without a lock, updates vanish.
B. The factory's FETCH_HEAD window, in scratch repos: the adapter runs `git fetch <clone> <branch>` then
   `git rev-parse FETCH_HEAD`. Another `git fetch` in the same repo in between (the operator, an editor's
   auto-fetch) rewrites FETCH_HEAD, so the adapter reads, and would push, someone else's commit.
   The fix: fetch into a ref of your own (`git fetch <clone> <branch>:refs/factory/<run>`) and read that."""
import os
import subprocess
import tempfile
import threading
import time

tmp = tempfile.mkdtemp()
counter = os.path.join(tmp, "count")


def run(locked):
    open(counter, "w").write("0")
    lock = threading.Lock()

    def work():
        for _ in range(50):
            if locked:
                lock.acquire()
            n = int(open(counter).read())
            time.sleep(0.0001)  # the window between read and write
            open(counter, "w").write(str(n + 1))
            if locked:
                lock.release()
    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return int(open(counter).read())


print(f"A  no lock:   counter = {run(False)} (expected 400)")
print(f"A  with lock: counter = {run(True)} (expected 400)")


def git(cwd, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x", *a], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


trusted, agent, other = (os.path.join(tmp, d) for d in ("trusted", "agent-clone", "other-clone"))
for d in (trusted, agent, other):
    os.makedirs(d)
    git(d, "init", "-q", "-b", "main")
for d, msg in ((agent, "agent's work"), (other, "something else")):
    open(os.path.join(d, "f"), "w").write(msg)
    git(d, "add", "-A")
    git(d, "commit", "-qm", msg)
agent_sha, other_sha = git(agent, "rev-parse", "HEAD"), git(other, "rev-parse", "HEAD")

git(trusted, "fetch", "--quiet", agent, "main")      # adapter: fetch the agent's branch
git(trusted, "fetch", "--quiet", other, "main")      # meanwhile: another fetch in the same repo
read = git(trusted, "rev-parse", "FETCH_HEAD")       # adapter: read what it fetched
print(f"\nB  adapter pattern: FETCH_HEAD is the agent's commit = {read == agent_sha}; someone else's = {read == other_sha}")

git(trusted, "fetch", "--quiet", agent, "main:refs/factory/run1")   # fix: a ref only this run writes
git(trusted, "fetch", "--quiet", other, "main")
read = git(trusted, "rev-parse", "refs/factory/run1")
print(f"B  own ref:         refs/factory/run1 is the agent's commit = {read == agent_sha}")
