"""Production incidents: customer impact is governed by the timeline, not by how clever the eventual fix is.
Impact lasts from when the problem starts to when it STOPS HURTING USERS -- which is the moment you mitigate,
not the moment you find root cause. Two SRE rules fall out of the arithmetic:
  1. Detection dominates. An incident nobody detects runs until a human stumbles on it.
  2. Mitigate before you diagnose. Stopping the bleeding (roll back, fail over, disable the feature) ends user
     impact immediately; root-causing can then happen off the clock.

Model one incident that begins at t=0, under three responses. Numbers in minutes; impact = user-facing minutes.
No external calls; pure arithmetic."""

START = 0

# shared timings (minutes)
DETECT_MONITORED = 2      # alerting fires quickly
DETECT_BY_LUCK = 180      # no alert: someone eventually notices
DIAGNOSE = 45             # time to find the root cause
FIX = 20                  # time to write and ship the real fix
MITIGATE = 5              # time to roll back / fail over (stops user impact)

scenarios = {
    "undetected (no alerting)":      DETECT_BY_LUCK + DIAGNOSE + FIX,     # impact until noticed, then fixed
    "detected, diagnose-first":      DETECT_MONITORED + DIAGNOSE + FIX,   # fix root cause while users suffer
    "detected, mitigate-first":      DETECT_MONITORED + MITIGATE,         # roll back, THEN diagnose off the clock
}

print("customer-impact minutes per response to the same incident:")
best = min(scenarios.values())
for name, impact in scenarios.items():
    bar = "#" * (impact // 5)
    print(f"  {name:28s} {impact:4d} min  {bar}")
print(f"\nmitigate-first ends impact at {scenarios['detected, mitigate-first']} min vs "
      f"{scenarios['detected, diagnose-first']} min diagnosing first "
      f"({scenarios['detected, diagnose-first'] - scenarios['detected, mitigate-first']} min saved); "
      f"no alerting makes the SAME bug a {scenarios['undetected (no alerting)']}-min incident.")
