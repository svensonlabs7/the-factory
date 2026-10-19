# 96. Clock Skew

Track: H. Distributed systems · Status: proven · Updated: 2026-10-19

## What it is
Every machine's clock drifts. NTP keeps it near true time, but each machine is a little off (skew), and corrections can step the clock forward or backward. So can leap seconds, VM migration and wake from sleep. Two facts follow.

**Timestamps from different machines cannot be compared exactly.** Lamport's 1978 paper shows that "happened before" is a partial order, defined by causality rather than by wall-clock time. Logical clocks (Lamport clocks, vector clocks) order events consistently with cause and effect, where physical timestamps can put an effect before its cause.

**A wall clock is the wrong tool for measuring durations or deadlines on one machine.** PEP 418 introduced `time.monotonic()` for "timeout and scheduling, not affected by system clock updates", because the system time "can be set manually by the system administrator or automatically by a NTP daemon". Cloudflare's 2017 leap-second outage came from `time.Now().Sub(start)` going negative. The negative durations reached a random-number call that panicked, and DNS resolutions failed for up to 0.2% of queries.

## When it is worth it
Care about skew wherever time crosses a machine boundary or decides an outcome:
- signed requests with freshness windows, token expiry (`exp`, `nbf`), and certificate validity;
- ordering events from several machines, and last-write-wins;
- distributed leases and locks;
- timeouts, deadlines and durations within one process.

The cheap rules: monotonic clocks for durations, NTP on every host, windows wide enough for realistic skew, and logical ordering where causality matters. TrueTime-style bounded-uncertainty clocks and hybrid logical clocks are for globally distributed databases.

## How it fails
- **Freshness window narrower than real skew:** a sender whose clock is 5 minutes off has every signed request rejected as stale, or every token treated as expired or not yet valid.
- **Deadline on the wall clock:** an NTP step or a wake from sleep jumps the clock → a timeout fires instantly, or never fires (proof B).
- **Negative or huge durations:** `end - start` on wall time across a step → bogus metrics or crashes (Cloudflare 2017).
- **Ordering by timestamps across machines:** a reply appears before its request in merged logs, or last-write-wins keeps the older write (proof C).
- **Leases trusted across machines:** a lock holder thinks its lease is valid while the lock service's clock says it expired → two holders (038-distributed-locks.md).
- **Local time in timestamps:** daylight-saving changes and zones scramble ordering (021-cron-jobs.md).

## Review checklist
- [ ] **Are durations, timeouts and deadlines measured on a monotonic clock?** · Applies when: the diff adds or changes code that measures elapsed time or enforces a deadline within one process. · Block if: that code subtracts or compares `time.time()` (or another wall clock) instead of `time.monotonic()`. Untouched existing uses are tracked in the card, not blocked.
- [ ] **Does a cross-machine freshness or expiry check allow for skew?** · Applies when: the diff validates timestamps from another machine (signatures, tokens, certificates). · Block if: the window has no allowance for skew, or the allowance is smaller than the hosts' realistic offset.
- [ ] **Is cross-machine ordering logical, not physical?** · Applies when: the diff orders, merges or resolves conflicts between events from several machines. · Block if: it relies on wall-clock timestamps where reordering would change correctness (last-write-wins, causal logs), with no logical clock or single sequencer.
- [ ] **Are timestamps stored in UTC?** · Applies when: the diff records or compares times. · Block if: it stores local time, or a format without a zone.
- [ ] **Are synchronized clocks a stated dependency?** · Applies when: the diff depends on two hosts agreeing on time (expiry, leases, signatures). · Block if: nothing ensures NTP on those hosts, and nothing alerts on large offset.

## In the factory
- `/trigger` signatures must fall within `REPLAY_WINDOW = 300` s of the adapter's clock (`factory/intake/webhook_adapter.py:74,241`). That is right. A ±300 s allowance is generous against this host's measured offset of +8.8 ms (±19 ms, `sntp time.apple.com`). A sender more than 5 minutes off is locked out entirely, which is what a replay window must do (proof A).
- Timestamps are UTC epoch seconds, or `gmtime` for `alive_at` (`:139`, `:159`). Right.
- Durations and deadlines use the wall clock:
  - the gate wait (`deadline = time.time() + CHECKS_TIMEOUT`, `:357-358`);
  - round durations (`:420`, `:444-446`);
  - the PR cache TTL (`:661`).

  A forward step longer than the deadline ends a gate wait at once and errors the run, even if the checks had finished (proof B). That is acceptable on this host, which never sleeps (`pmset`: `sleep 0`) and keeps NTP's small slews. If the host can sleep or its clock can step, these should move to `time.monotonic()`.
- Joining the factory's records with GitHub Actions timestamps crosses machines. 060-distributed-tracing.md reads that join with seconds of tolerance, not as an exact order.
- Not applicable at today's load: logical clocks, hybrid clocks and lease fencing. There is one host and one writer.

## Proof
`pytest -s scratchpad/mastery/096_clock_skew.py` (Python 3.11). A and B use the real adapter through `tests/test_adapter.py`'s fixture. In B, the module's `time` is replaced by a stand-in whose wall clock jumps 1,300 s after the first poll, while monotonic time is untouched. The fixture's `CHECKS_TIMEOUT` is 3 s; the jump also exceeds production's 1,200 s.
```
A  sender clock skew: +0 s -> 202; +299 s -> 202; +301 s -> 401 Stale request; -301 s -> 401 Stale request
B  wall clock steps +1,300 s during the wait: 'timed out waiting for checks' after 0.000 s of real time and 2 gh calls (CHECKS_TIMEOUT 3 s)
C  ordered by wall-clock timestamps: ['request received', 'reply sent', 'request sent', 'reply received']
C  ordered by Lamport clocks:        ['request sent', 'request received', 'reply sent', 'reply received']
```
Host offset: `sntp time.apple.com` reported `+0.008758 +/- 0.018989`.

## Related
060-distributed-tracing.md, 038-distributed-locks.md, 070-jwt-rotation.md, 021-cron-jobs.md, 035-eventual-consistency.md, 011-timeouts.md

## Sources
- Leslie Lamport, "Time, Clocks, and the Ordering of Events in a Distributed System", CACM 1978: https://lamport.azurewebsites.net/pubs/time-clocks.pdf
- PEP 418, "Add monotonic time, performance counter, and process time functions": https://peps.python.org/pep-0418/
- "How and why the leap second affected Cloudflare DNS", Cloudflare Blog: https://blog.cloudflare.com/how-and-why-the-leap-second-affected-cloudflare-dns/
