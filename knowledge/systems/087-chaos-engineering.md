# 87. Chaos Engineering

Track: L. Operations · Status: proven · Updated: 2026-10-19

Triggers: files `^factory/build/egress\.sh$` · lines `(?i)chaos|fault.?inject|sigkill|os\.kill|docker (stop|kill)`

## What it is
Chaos engineering is the discipline of deliberately injecting real-world faults into a system to verify that the resilience you *believe* you have is actually there — before a real failure proves it is not. The method (principlesofchaos.org) is scientific: state a **steady-state hypothesis** (a measurable "healthy" metric — a success rate, a latency target), **inject a fault** that mimics a real event (a dependency outage, a slow network, a killed instance — Netflix's Chaos Monkey terminates instances; AWS FIS injects faults), and check whether the hypothesis still holds. If it does, the resilience is real; if it breaks, you have found a weakness cheaply, in a controlled window, instead of during an incident (proof). The non-negotiable safety rule is **minimise the blast radius**: run on a small slice of traffic, during business hours with people watching, with an abort switch, so the experiment itself cannot become the outage. It verifies, it does not create, resilience — the fallbacks, retries and failover (010, 012, 085) must already exist; chaos checks they work.

## When it is worth it
- Worth it for systems complex enough that failure modes are **emergent** — many services, retries, timeouts and fallbacks whose interactions no one can fully reason about, where the only way to know the system survives a dependency loss is to take the dependency away and watch. Mature orgs automate it continuously (Chaos Monkey in production).
- Over-engineering for a small, well-understood system whose failure modes you can enumerate by reading the code. Running a chaos platform against a single-operator webhook is ceremony: there is no emergent complexity to discover. What *does* transfer at any size is the method — **a steady-state hypothesis plus an injected fault**, run once, by hand, to confirm a specific safeguard works. A test that kills a dependency and asserts graceful degradation is chaos engineering in its proportionate form.

## How it fails
- **Chaos without a hypothesis:** faults are injected with no defined steady state to measure against, so the run proves nothing — it is just breakage.
- **No blast-radius limit:** the experiment runs against all traffic with no abort, so a found weakness becomes a real, full-scale incident (the thing it was meant to prevent).
- **Testing resilience that was never built:** injecting faults when there is no fallback/retry to exercise just confirms the obvious outage; chaos verifies safeguards, it does not substitute for them.
- **Unmonitored experiment:** without the metrics to see the steady state, you cannot tell whether the hypothesis held, and cannot abort in time (058-monitoring.md).
- **Run in an environment unlike production:** faults injected only in a toy environment miss the real interactions, giving false confidence.
- **No follow-through:** a weakness is found and not fixed (turned into a tracked action item — 111-postmortems.md).

## Review checklist
- [ ] **Does a fault-injection test assert a defined steady state?** · Applies when: the diff adds a test or experiment that injects a failure (kills a dependency, drops a connection). · Block if: it injects the fault but asserts no measurable healthy-state hypothesis, so a pass proves nothing.
- [ ] **Is the blast radius bounded and abortable?** · Applies when: the diff adds fault injection against a shared or live environment. · Block if: it can affect all traffic with no slice limit, no monitoring of the steady state, and no abort — so the experiment can become the incident.
- [ ] **Does the safeguard being tested actually exist?** · Applies when: the diff adds a chaos experiment for a failure mode. · Block if: there is no fallback/retry/failover for that mode to exercise — build the resilience before testing it.
- [ ] **Is a chaos platform proportionate here?** · Applies when: the diff introduces continuous/automated chaos tooling. · Block if: the system's failure modes are small and enumerable by reading the code, where a single hand-run hypothesis-plus-fault test would give the same assurance without the platform.

## In the factory
- **No chaos platform, and that is right at one host** — the failure modes are enumerable by reading the code (and, in fact, this whole `knowledge/systems/` effort enumerates them). Running Chaos Monkey against a single webhook would be ceremony with nothing emergent to find.
- **But the factory already uses the chaos *method* in its proportionate form, which is the valuable part:**
  - **`egress.sh` is a standing chaos experiment with a steady-state hypothesis.** Its hypothesis is "the sandbox network cannot reach the internet directly"; every run it *injects the test* — a container tries `curl https://example.com` and the run is aborted unless that connection **fails** — and it also asserts the proxy *can* reach an allowed host. That is inject-fault-and-check-hypothesis, run on every build, fail-closed (`factory/build/egress.sh:30-50`, 080-ssrf.md).
  - **The systems-mastery experiments themselves** are hypothesis-plus-fault tests: each card injects a specific failure in the scratchpad and asserts the fix holds. That is chaos engineering's method applied to learning.
- **The blast-radius rule is respected by construction:** experiments run in the scratchpad, never against the live adapter, and `egress.sh`'s probe uses throwaway containers — the experiment cannot take the factory down.
- Not applicable at today's load: Chaos Monkey, AWS FIS, automated/continuous chaos, production fault injection against live traffic.

## Proof
`python3 knowledge/systems/proofs/087_chaos.py`, a service depending on D, with the steady-state hypothesis "success >= 99%":
```
Inject 'dependency D is down' on 100% of traffic (full experiment):
   fallback=False: success    0% -> hypothesis VIOLATED (weakness found)
   fallback=True : success  100% -> hypothesis HOLDS (resilience real)

Blast-radius control: no fallback, but inject on only 5% of traffic:
   success   95% -> worst-case impact capped at 5%; the experiment is abortable before it becomes an incident
```
Injecting the dependency outage reveals the truth the code alone did not guarantee: without a fallback the steady state collapses (the believed resilience was absent), with one it holds. Limiting the fault to 5% of traffic bounds the worst case so the experiment cannot itself become the incident. The method is hypothesis → inject → observe → bound the blast radius.

## Related
080-ssrf.md, 010-circuit-breakers.md, 012-retries.md, 085-failover.md, 057-liveness-readiness-probes.md, 058-monitoring.md, 111-postmortems.md

## Sources
- "Principles of Chaos Engineering": https://principlesofchaos.org/
- "Chaos Engineering" (Chaos Monkey) and AWS Fault Injection Service: https://netflix.github.io/chaosmonkey/ and https://docs.aws.amazon.com/fis/latest/userguide/what-is.html
