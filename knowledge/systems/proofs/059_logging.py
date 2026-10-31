"""Logging. A: log injection, plain text vs JSON lines (the factory writes rejected.jsonl and actions.jsonl as JSON).
B: the cost of an access log with no timestamps and no rotation, from the factory's real intake.out.log."""
import io
import json
import logging
import sys

hostile_task = 'Add a page\n2026-10-18 03:12:09 [INFO] Run 1a2b3c4d completed (pr=https://github.com/x/y/pull/1)'

buf = io.StringIO()
logger = logging.getLogger("demo")
handler = logging.StreamHandler(buf)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.info("Queued run 9f9f9f9f: task=%s", hostile_task)
lines = buf.getvalue().splitlines()
print(f"A  plain text: 1 event became {len(lines)} lines; a reader sees a forged 'completed' entry: {any('completed' in l and l.startswith('2026-10-18 03:12:09') for l in lines)}")

jl = json.dumps({"time": 1792258094.2, "event": "queued", "task": hostile_task})
print(f"A  JSON line:  1 event is {len(jl.splitlines())} line; the newline is escaped inside the field: {chr(92) + 'n' in jl}")

log = open(sys.argv[1]).read().splitlines()
timed = sum(1 for l in log if l[:4].isdigit())
size = sum(len(l) + 1 for l in log)
print(f"B  {sys.argv[1].split('/')[-1]}: {len(log)} lines, {timed} with a timestamp; {size / 1024:.0f} KB so far")
dash_lines_per_day = 86400 / 15  # the dashboard polls /command/data every 15 s while open
print(f"B  with the dashboard open: ~{dash_lines_per_day:.0f} lines/day, ~{dash_lines_per_day * 85 / 1e6 * 365:.0f} MB/year, never rotated")
