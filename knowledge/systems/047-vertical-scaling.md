# 47. Vertical Scaling

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)colima (start|edit)|--cpus?\b|--memory\b|mem_limit|cpu_count\(`

## What it is
Vertical scaling (scaling up) means giving one machine or process more resources: more CPU cores, more memory, faster disks or a bigger instance type. Nothing about the architecture changes, which makes it the simplest scaling move and usually the first.

It has hard limits:
- **Amdahl's law:** more cores speed up only the parallel part of the work, so a workload that is 20% serial can never run more than 5 times faster, however many cores it gets.
- **Visible resources:** the workload must actually see and use the extra resources. A container, VM or runtime with its own CPU or memory cap gains nothing from a bigger host.
- **Ceilings and single points of failure:** there is a largest machine, and one machine is still one point of failure.
- **Restarts:** resizing usually needs one. Kubernetes' Vertical Pod Autoscaler applies new requests by recreating pods.

Before scaling anything, find the bottleneck. Brendan Gregg's USE method: "for every resource, check utilization, saturation, and errors".

## When it is worth it
Scale up first when one node's measured resource (CPU, memory, I/O) is saturated, the workload can use more of it, and a bigger node is cheap compared with redesigning for many nodes. Below that point it is wasted spend. It is over-engineering when the bottleneck is elsewhere: an external API, a lock, a quota, or serial code that cannot use more cores. Horizontal scaling (046-horizontal-scaling.md) is for when one node's ceiling, or its failure, is the problem.

## How it fails
- **Scaling the wrong resource:** more CPU for a workload waiting on the network, a lock or an external quota → no gain.
- **The workload cannot see the new resources:** a VM, container limit or `--cpus` cap stays at its old size while the host grows → no gain (proof B).
- **Serial fraction:** past a few cores, speedup flattens far below the core count (Amdahl; proof A).
- **Heterogeneous cores:** performance and efficiency cores make "N cores" worth less than N fast ones.
- **Memory scaled, but not the configuration:** the JVM heap, worker counts or pool sizes are left at the old values.
- **Resize needs downtime:** changing the instance or VM size restarts the service, and in-flight work is lost (054-rolling-deployments.md).

## Review checklist
- [ ] **Is the bottleneck measured before resources are added?** · Applies when: the diff raises CPU, memory or instance size, or a VM or container limit. · Block if: no utilization or saturation measurement (USE) shows that resource is the bottleneck. · tripwire
- [ ] **Can the workload use what is added?** · Applies when: the diff adds cores or memory. · Block if: the workload's parallelism, worker count, heap or container limit stays at the old value, or its serial fraction caps the gain far below the cost.
- [ ] **Do inner limits move with the outer one?** · Applies when: the diff resizes a host, VM or node. · Block if: a nested limit (container `--cpus`, VM CPUs or memory, a runtime cap) still bounds the workload.
- [ ] **Is the resize's restart planned?** · Applies when: the diff changes the size of a running service's machine or VM. · Block if: the restart would kill in-flight work, with no drain or idle check.

## In the factory
- The sandboxed builds run inside the Colima VM, sized at 2 CPUs and 4 GiB (`colima list`, and `docker info`: 2 CPUs, 4,094,447,616 bytes) on a 10-core Apple M4 with 16 GiB. Builds see a fifth of the host's cores.
  - Whether that matters is unmeasured. The 315 s and 406 s build rounds are mostly the agent waiting on Claude's API.
  - No run log shows an out-of-memory kill (`Killed`, `OOM`, exit 137).
  - The binding resource is plan usage (092-throughput.md).
- If builds ever become CPU-bound, resizing Colima (`colima stop` then `colima start --cpu N --memory M`) is the cheap first lever. Measure first: `docker stats` on the sandbox during a build gives its utilization. The resize restarts the VM, so do it only when no run is in flight (054-rolling-deployments.md).
- The adapter itself needs a fraction of one core (092-throughput.md).
- Not applicable at today's load: bigger hosts, instance resizing and vertical autoscaling.

## Proof
`python -I knowledge/systems/proofs/047_vertical.py` runs 8 CPU-bound chunks across N worker processes, plus a serial step sized to 20% of the one-worker time. It ran on the host (Python 3.11) and inside the Colima VM in the local `python:3.12` image (`docker run -i --network none`, script on stdin):
```
host: 10 CPUs visible; 1 worker  2.87 s
host: 2 workers -> speedup 1.56x (Amdahl with 20% serial: 1.67x)
host: 4 workers -> speedup 2.03x (Amdahl with 20% serial: 2.50x)
host: 8 workers -> speedup 2.41x (Amdahl with 20% serial: 3.33x)
colima-vm: 2 CPUs visible; 1 worker  4.27 s
colima-vm: 2 workers -> speedup 1.47x (Amdahl with 20% serial: 1.67x)
colima-vm: 4 workers -> speedup 1.30x (Amdahl with 20% serial: 2.50x)
colima-vm: 8 workers -> speedup 1.29x (Amdahl with 20% serial: 3.33x)
```
- Inside the VM, more workers stop helping at 2: the workload sees only the VM's cores.
- On the host, the speedup falls below Amdahl's prediction past 2 workers. The M4 mixes performance and efficiency cores, and pool start-up is part of the serial cost.
- The per-core gap between host and VM includes different Python versions (3.11 against 3.12), so it is not a clean VM-overhead figure.

## Related
046-horizontal-scaling.md, 045-autoscaling.md, 092-throughput.md, 054-rolling-deployments.md, 088-cost-optimization.md

## Sources
- "The USE Method", Brendan Gregg: https://www.brendangregg.com/usemethod.html
- "Vertical Pod Autoscaler", Kubernetes autoscaler README: https://github.com/kubernetes/autoscaler/blob/master/vertical-pod-autoscaler/README.md
