"""Serverless limits.
A. A hard execution limit, enforced the way a platform does: the process is killed at the limit. A 12-step job
   (0.25 s per step) under a 2 s limit: run straight through it loses everything; checkpointing after each step and
   re-invoking resumes and finishes (the Step Functions / durable-execution pattern). Real processes, real SIGKILL.
B. The factory's real workloads against published limits (Lambda: 900 s timeout, 6 MB sync payload, 10 GB image;
   Workers: 128 MB memory, 30 s default CPU)."""
import json
import os
import subprocess
import sys
import tempfile
import time

JOB = r"""
import json, os, sys, time
state_path, use_checkpoint = sys.argv[1], sys.argv[2] == "1"
done = json.load(open(state_path))["done"] if use_checkpoint and os.path.exists(state_path) else 0
for step in range(done, 12):
    time.sleep(0.25)
    done = step + 1
    if use_checkpoint:
        json.dump({"done": done}, open(state_path, "w"))
print(json.dumps({"finished": done == 12, "done": done}))
"""


def invoke(state, checkpoint, limit=2.0):
    try:
        out = subprocess.run([sys.executable, "-c", JOB, state, "1" if checkpoint else "0"], capture_output=True, text=True, timeout=limit)
        return json.loads(out.stdout)
    except subprocess.TimeoutExpired:            # the platform kills the invocation at its limit
        return {"finished": False, "killed": True}


for checkpoint in (False, True):
    state = tempfile.mktemp()
    invocations, result = 0, {}
    while invocations < 4 and not result.get("finished"):
        result = invoke(state, checkpoint)
        invocations += 1
    saved = json.load(open(state))["done"] if os.path.exists(state) else 0
    print(f"A  {'checkpoint + re-invoke' if checkpoint else 'straight through     '}: {invocations} invocations, finished {result.get('finished')}, steps kept {saved if checkpoint else 0}/12")

build_rounds = [314.7, 405.6]
print(f"B  build round {max(build_rounds):.0f} s (cap 1800 s) vs Lambda 900 s max: {'fits' if max(build_rounds) < 900 else 'exceeds'}; the cap itself exceeds it by {1800 - 900} s")
print("B  sandbox needs a Docker daemon and a 9.06 GB agent-server image: Lambda gives no Docker daemon; image limit 10 GB")
print("B  /command/data response ~6 KB vs 6 MB sync payload; /trigger body ~100 B: fit")
