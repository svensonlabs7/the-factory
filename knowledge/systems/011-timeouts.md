# 11. Timeouts

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
A timeout is the longest a caller will wait for something outside its control: a network call, a subprocess, a container, a lock, a queue. When it expires, the caller stops waiting, and it should also stop the work it started, then report what timed out. Without one, a single stuck dependency holds a thread, a connection or a queue slot forever, and everything queued behind it waits too.

## When it is worth it
Always, for any call that crosses a process or network boundary: it costs one argument. Pick a generous fixed limit from observed durations (factory rounds take 5 to 7 minutes and are capped at 30). Tuning limits to a latency percentile and a target false-timeout rate is worth it only with real latency metrics and many callers. A deadline object passed through every layer, gRPC style, is over-engineering on one host with one queue: one outer deadline per unit of work, with shorter inner limits, is enough.

## How it fails
- **No timeout:** a dependency accepts the connection and never answers → the caller waits forever, and on a serial queue every later run waits too.
- **Stops the waiter, not the work:** `Popen.wait(timeout=)`, `communicate(timeout=)` and `future.result(timeout=)` only raise; the child, thread or container keeps running and keeps spending.
- **Kills only the direct child:** `subprocess.run(timeout=)` SIGKILLs the child it started; a grandchild (`uv` → `python` → Docker container) survives as an orphan.
- **Measures the wrong thing:** urllib's `timeout` limits each socket operation, so a server that drips a byte every half second never trips it. `acp_prompt_timeout` is an idle timeout, so a busy agent never trips it.
- **Inner limit longer than outer:** the outer deadline fires first, so the inner cleanup never runs.
- **Too short:** normal slow cases fail, and with retries a small slowdown turns into a flood of repeated work.

## Review checklist
- [ ] **Does every new outbound call have a timeout?** · Applies when: the diff adds or changes an HTTP, socket, subprocess, `docker`, `git`, `gh`, database or lock call, or any wait. · Block if: the call can block with no timeout and no enclosing deadline that also stops it.
- [ ] **Does the timeout stop the work, not only the wait?** · Applies when: the diff handles a timeout on a subprocess, container, thread or task. · Block if: on timeout the code only stops waiting, or kills only the direct child of something that can spawn its own children or containers.
- [ ] **Is each inner limit shorter than the deadline around it?** · Applies when: a timed call runs inside another timed operation. · Block if: the inner timeout is greater than or equal to the enclosing one.
- [ ] **Is a timeout reported as a timeout?** · Applies when: the diff adds a timeout handler. · Block if: the timeout is swallowed, retried with no limit, or reported without naming the operation and the limit that expired.
- [ ] **Does the code know what its timeout measures?** · Applies when: the diff relies on a library's timeout parameter. · Block if: code or a comment treats a connect, per-read or idle timeout as a total deadline.
- [ ] **Does a long-running CI job set `timeout-minutes`?** · Applies when: the diff adds or edits a GitHub Actions job that calls an LLM, builds or runs untrusted code, or waits on an external service. · Block if: that job has no `timeout-minutes`.

## In the factory
- `factory/intake/webhook_adapter.py:65,316-318`: every `git` and `gh` call gets `COMMAND_TIMEOUT` (300 s), and a hang is reported as an error naming the command. Right.
- `factory/intake/webhook_adapter.py:357-372`: waiting for gate checks has one total deadline, `CHECKS_TIMEOUT` (20 min). Right.
- `factory/intake/webhook_adapter.py:428-445,297-310`: a round past `AGENT_TIMEOUT` stops the container, then SIGTERMs and SIGKILLs the whole process group. This was verified with a real sandbox on 2026-10-18 (#56). Right.
- `factory/intake/webhook_adapter.py:526`: a timeout ends the run as `timeout` with a reason naming the round and the limit. Right.
- `factory/build/egress.sh:33,37`: the egress checks use `curl -m 5` and `-m 8`. Right.
- `factory/build/run_agent.py:31`: `egress.sh` runs with no timeout of its own, but `AGENT_TIMEOUT` encloses it. Acceptable.
- Gap: `factory/build/run_agent.py:34-35` and `webhook_adapter.py:53` treat `acp_prompt_timeout` as a deadline. It is an idle timeout (see GAPS.md).
- Gap: no GitHub Actions job sets `timeout-minutes` (see GAPS.md).

## Proof
`python3 -I scratchpad/mastery/011_timeouts.py`:
```
A-fail no timeout: still waiting after 5s = True
A-fix  timeout=1: timeout after 1.0s
B-fail run(timeout=1): grandchild still running = True ['69650']
B-fix  new session + killpg: grandchild still running = False
C-fail timeout=1 per operation: finished after 4.0s, no timeout raised (8 bytes)
C-fix  total deadline 1.5s: gave up after 1.5s
```
C-fix only stops the waiting; the reading thread runs on until the server finishes, which is failure mode 2. The full fix closes the socket at the deadline.

Real sandbox: `run_agent.py <workdir> "<run sleep 600 in the foreground>" 40` exited 0 after 625 s. The 40-second `acp_prompt_timeout` never fired, and the run ended only when the tool's own 10-minute command limit ended the sleep.

## Related
012-retries.md, 013-exponential-backoff.md, 014-idempotency.md, 010-circuit-breakers.md, 044-backpressure.md, 101-webhooks.md, 056-health-checks.md, 057-liveness-readiness-probes.md, 006-ci-cd.md

## Sources
- Marc Brooker, "Timeouts, retries, and backoff with jitter", Amazon Builders' Library: https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
- "Addressing Cascading Failures", Google SRE book: https://sre.google/sre-book/addressing-cascading-failures/
- Python `subprocess` documentation: https://docs.python.org/3/library/subprocess.html
- OpenHands SDK, `ACPAgent._await_with_idle_deadline` (openhands-sdk 1.54.0, `sdk/agent/acp_agent.py`)
