# 45. Autoscaling

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)autoscal|horizontalpodautoscaler|min_?instances|max_?instances`

## What it is
Autoscaling changes capacity automatically as load changes: adding instances when a metric rises above target, removing them when it falls. Kubernetes' Horizontal Pod Autoscaler is the reference design. It computes `desiredReplicas = ⌈currentReplicas × currentMetricValue / desiredMetricValue⌉` and "skips any scaling action if the ratio is sufficiently close to 1.0 (within a configurable tolerance, 0.1 by default)". It damps the loop in several ways:
- a downscale stabilization window, "which defaults to 5 minutes", so that "scaledowns will occur gradually, smoothing out the impact of rapidly fluctuating metric values";
- readiness and CPU-initialization delays (30 s and 5 minutes by default), so start-up spikes do not trigger more scaling.

An autoscaler is a feedback controller, with the usual failure modes of one. It reacts late, because new capacity takes time to become ready. It can oscillate when it chases noise. It can only scale what is actually horizontally scalable (046-horizontal-scaling.md).

## When it is worth it
Autoscaling is worth it when load varies a lot over hours or days, capacity costs money while idle, the service scales horizontally, and new instances become ready faster than the load changes. It needs a metric that tracks real saturation (CPU, queue depth, concurrency), not one that lags or saturates elsewhere. For steady or tiny loads, fixed capacity with headroom is simpler and cheaper. For spiky loads that arrive faster than instances start, pre-scaling or queueing is needed in addition.

## How it fails
- **Flapping:** the controller chases noisy metrics, adding and removing instances every few minutes → churn, cold caches and wasted start-ups (proof A: 56 changes in 20 minutes).
- **Too slow for the spike:** a step in load arrives faster than new instances become ready → requests fail or queue during warm-up, which is exactly when they matter (proof C).
- **Scaling on the wrong metric:** CPU stays low while the real bottleneck (a database, a lock, an external quota) saturates → the autoscaler adds instances that make it worse (046-horizontal-scaling.md).
- **Scale-in kills work:** removed instances are terminated mid-request or mid-job, with no drain (054-rolling-deployments.md).
- **Runaway scale-out:** a bug or retry storm inflates the metric → hundreds of instances and a large bill, with no maximum.
- **Stabilization overshoot:** damping keeps capacity at the recent peak → more instances than needed for a while (proof B ends at 18 replicas where 15 would do). That is the price of stability.

## Review checklist
- [ ] **Does the scaling metric track the real bottleneck?** · Applies when: the diff adds or changes an autoscaling policy. · Block if: the metric does not saturate when the service does (for example, CPU on an I/O- or quota-bound service), or the bottleneck is a shared resource that more instances would overload.
- [ ] **Are bounds and damping set?** · Applies when: the diff configures autoscaling. · Block if: there is no maximum instance count, or no downscale stabilization or cooldown, so a noisy or runaway metric can flap or explode capacity.
- [ ] **Can new capacity arrive before the load does?** · Applies when: the diff relies on autoscaling for load spikes. · Block if: instance start-up and readiness take longer than the spikes it must absorb, and there is no headroom, pre-scaling or queue.
- [ ] **Does scale-in drain work?** · Applies when: the diff lets the autoscaler remove instances that run requests or jobs. · Block if: removed instances are terminated without draining in-flight work.
- [ ] **Is autoscaling justified?** · Applies when: the diff introduces autoscaling. · Block if: load is steady or small enough that fixed capacity with headroom covers the peak. · tripwire

## In the factory
- The factory has no autoscaling, and should not. Capacity is fixed and small: one run worker (`factory/intake/webhook_adapter.py:151`), with admission caps of 5 in flight and 30 a day (`:72-73`) at a measured 1.4 runs a day (092-throughput.md). The adapter could not scale horizontally anyway (046-horizontal-scaling.md), and the binding resource, the Claude plan, has a fixed quota.
- The elastic part is GitHub's. Every CI job runs on a GitHub-hosted runner, and "each GitHub-hosted runner is a new virtual machine". So the six gate jobs of every PR get fresh, parallel capacity without the factory doing anything.
- The usage-limit pause (`USAGE_LIMIT_DEFAULT_WAIT`, `:61`) is the factory's only adaptive capacity behaviour: when the plan's quota is exhausted, it waits rather than failing.
- Not applicable at today's load: autoscalers, scaling policies and pre-scaling.

## Proof
`python3.11 -I knowledge/systems/proofs/045_autoscaling.py` is a seeded simulation of the HPA rule: a 15 s evaluation, a 0.1 tolerance, and a 60% CPU target with 100 req/s per replica. New replicas take 60 s to become ready. Load is noisy around 300 req/s, then steps to 900 req/s at 10 minutes:
```
A  no stabilization              :  56 replica-count changes in 20 min; final 12 replicas
B  300 s downscale stabilization :   4 replica-count changes in 20 min; final 18 replicas
C  step 300 -> 900 req/s with 60 s replica warm-up: 15,203 requests above ready capacity during the scale-up
```

## Related
046-horizontal-scaling.md, 047-vertical-scaling.md, 092-throughput.md, 054-rolling-deployments.md, 088-cost-optimization.md, 089-cold-starts.md

## Sources
- "Horizontal Pod Autoscaling", Kubernetes documentation: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
- "GitHub-hosted runners", GitHub Actions documentation: https://docs.github.com/en/actions/concepts/runners/github-hosted-runners
