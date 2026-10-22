"""Cron jobs.
A. Overlap: a scheduler fires a job every 0.5 s whose run takes 1.2 s. Each run is a real process doing a
   read-modify-write on a shared state file (as a sync or prune job would). Without a lock, runs overlap and updates
   are lost; with a non-blocking flock (skip if the previous run still holds it), at most one runs.
B. Local-time schedules across DST in America/New_York (this host's zone): a daily 02:30 job on spring-forward day,
   and a daily 01:30 job on fall-back day."""
import datetime as dt
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from zoneinfo import ZoneInfo

JOB = r"""
import fcntl, sys, time
from pathlib import Path
state, lock, use_lock, log = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] == "1", Path(sys.argv[4])
if use_lock:
    fh = open(lock, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        with log.open("a") as f: f.write("skipped\n")
        sys.exit(0)
with log.open("a") as f: f.write("start\n")
n = int(state.read_text())
time.sleep(1.2)                      # the job's real work
state.write_text(str(n + 1))
with log.open("a") as f: f.write("end\n")
"""


def schedule(use_lock):
    d = Path(tempfile.mkdtemp())
    (d / "state").write_text("0")
    (d / "job.py").write_text(JOB)
    procs = []
    for _ in range(8):                                   # 8 ticks, 0.5 s apart
        procs.append(subprocess.Popen([sys.executable, "-I", str(d / "job.py"), str(d / "state"), str(d / "lock"), "1" if use_lock else "0", str(d / "log")]))
        time.sleep(0.5)
    for p in procs:
        p.wait()
    events = (d / "log").read_text().split()
    running = peak = 0
    for e in events:
        running += {"start": 1, "end": -1}.get(e, 0)
        peak = max(peak, running)
    ran = events.count("start")
    print(f"A  {'flock, skip if busy' if use_lock else 'no lock':<20}: {ran} runs, {events.count('skipped')} skipped, peak concurrent {peak}, counter {(d / 'state').read_text()} (should equal runs: {ran})")


schedule(False)
schedule(True)

ny = ZoneInfo("America/New_York")
spring, fall = dt.date(2026, 3, 8), dt.date(2026, 11, 1)
t = dt.datetime.combine(spring, dt.time(2, 30), tzinfo=ny)
round_trip = t.astimezone(dt.timezone.utc).astimezone(ny)
print(f"B  daily 02:30 on {spring}: 02:30 does not exist; it resolves to {round_trip:%H:%M %Z} (the job runs at the wrong time, or is skipped by cron)")
first = dt.datetime.combine(fall, dt.time(1, 30, fold=0), tzinfo=ny).astimezone(dt.timezone.utc)
second = dt.datetime.combine(fall, dt.time(1, 30, fold=1), tzinfo=ny).astimezone(dt.timezone.utc)
print(f"B  daily 01:30 on {fall}: 01:30 happens twice, at {first:%H:%M} and {second:%H:%M} UTC (a run per occurrence = twice)")
print(f"B  in UTC: 06:30 UTC every day exists exactly once on both dates")
