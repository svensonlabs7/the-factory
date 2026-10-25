# 8. Kubernetes

Track: K. Infrastructure · Status: proven · Updated: 2026-10-19

Triggers: files `(^|/)(k8s|kubernetes|manifests)/` · lines `^\s*kind:\s*(Deployment|StatefulSet|DaemonSet|Pod|Ingress)\b|apiVersion:\s*apps/|kubectl ` · tripwire

## What it is
Kubernetes (k8s) is a container orchestrator: you declare the desired state of your workloads as objects (a Deployment wanting 3 replicas, a Service exposing them, a ConfigMap, resource limits) and k8s's **controllers** run continuous **reconciliation loops** that observe actual state and act to close the gap. That control model is the whole point. A **Pod** is the smallest unit (one or more containers sharing a network namespace); a **Deployment** manages a replica set of pods and does rolling updates (054-rolling-deployments.md); a **Service** gives a stable virtual address and load-balances across pods (003-load-balancing.md); the **scheduler** places pods on nodes by their resource requests; **probes** decide readiness and liveness (057-liveness-readiness-probes.md); **HPA** autoscales replicas (045-autoscaling.md). Because reconciliation is continuous, k8s self-heals: kill a pod and the Deployment recreates it; change the replica count and it converges (proof). The price is a large, complex distributed system (etcd, API server, controllers, networking) that is itself infrastructure to run.

## When it is worth it
- Worth it when you run **many containerised services across many nodes** and need their lifecycle managed: self-healing, rolling updates, horizontal autoscaling, service discovery and bin-packing across a fleet. At that scale the reconciliation model earns its complexity, and a managed control plane (EKS/GKE/AKS) removes most of the operational burden.
- Over-engineering — severely — for a **single host or a handful of containers**. k8s adds etcd, an API server, a scheduler, a CNI, and a steep operational surface to manage workloads that `systemd`/launchd, `docker run --restart`, or Docker Compose handle with a fraction of the moving parts. Running a one-node cluster to host one service means operating a distributed system to avoid a restart policy. The *idea* (declare desired state; let a loop reconcile it) is worth borrowing at any size; the platform is not.

## How it fails
- **Resource limits wrong:** a container with no memory limit (or a too-low one) is OOMKilled or starves neighbours; requests set wrong wreck scheduling and bin-packing.
- **Probes misconfigured:** a liveness probe shorter than real startup kills pods in a crash loop; a readiness probe that never passes takes a service out of rotation (057-liveness-readiness-probes.md).
- **Reconciliation fights manual changes:** someone edits a resource `kubectl edit` or by hand; the controller reverts it to the declared state, so out-of-band fixes vanish (104-infrastructure-as-code.md: drift).
- **etcd/control-plane problems:** etcd is the cluster's source of truth; losing or corrupting it, or losing quorum, breaks the whole cluster (033-leader-election.md, 032-replication.md).
- **Networking and config complexity:** misconfigured Services, Ingress, NetworkPolicies or DNS silently blackhole traffic; the surface area makes misconfiguration the common failure.
- **Cost and cognitive load:** the cluster itself consumes resources and expertise disproportionate to a small workload.

## Review checklist
- [ ] **Do containers declare resource requests and limits?** · Applies when: the diff adds or changes a workload manifest (Deployment, Pod, etc.). · Block if: a container has no memory limit/request where contention or OOM is possible, so it can be OOMKilled or starve the node.
- [ ] **Do probes allow for real startup and mean what they check?** · Applies when: the diff sets liveness/readiness probes. · Block if: the liveness probe is shorter than measured startup (crash loop), or readiness passes before the service can actually serve (057-liveness-readiness-probes.md).
- [ ] **Is declared state the only source of truth?** · Applies when: the diff manages a resource that a controller reconciles. · Block if: the change is expected to be made by hand on the live cluster, where reconciliation will revert it.
- [ ] **Is Kubernetes proportionate to this workload?** · Applies when: the diff introduces k8s (or a one-node cluster) for a service. · Block if: a single host or few containers are involved and a restart policy / Compose / launchd would manage them, so the cluster is complexity without a fleet to justify it.

## In the factory
- **No Kubernetes, deliberately, and that is unarguably right.** The factory is one Mac running one adapter process and one sandbox container per build. A k8s cluster here would mean operating etcd, an API server and a scheduler to manage a single service — the textbook over-engineering this card warns about.
- **The factory already has the useful part — a reconciliation loop — without the platform.** launchd runs the adapter with `KeepAlive` (`com.svenson.factory-intake.plist:38`), so if the process dies it is restarted: a one-replica self-healing controller. The egress proxy container runs with `--restart unless-stopped` (`egress.sh`), the same idea at the container level. And `egress.sh` re-asserts the firewall rules every run, reconciling drift. These are the k8s control model applied at the right scale.
- **The analogues to k8s features already have cards:** rolling updates (054), readiness/liveness (057), autoscaling (045), service load-balancing (003) — each noted as not-applicable at one host. Kubernetes is where they would all be bought at once, if the factory ever grew into a fleet.
- Not applicable at today's load: Deployments, Services, Ingress, HPA, etcd, a scheduler, manifests.

## Proof
`python3 knowledge/systems/proofs/008_kubernetes.py`, a model of a Deployment's reconciliation loop vs a one-shot launcher, with random pod crashes:
```
A  self-healing under random crashes (desired=3):
   reconciler: running=3 (back to desired), total pods ever created=11
   one-shot  : running=0 (decayed, no recovery)
B  declarative scale (reconciler), no manual add/remove:
   desired=5 -> running=5
   desired=2 -> running=2
```
The reconciler observes the gap each tick and recreates crashed pods, so the running count returns to the declared 3 (11 pods were created over the run as crashes happened); the one-shot launcher starts 3 and decays to 0 because nothing drives it back. Changing the desired count makes the reconciler converge to 5 then 2 with no manual add/remove. Continuous reconciliation is what gives self-healing and declarative scaling.

## Related
007-docker.md, 104-infrastructure-as-code.md, 054-rolling-deployments.md, 057-liveness-readiness-probes.md, 045-autoscaling.md, 003-load-balancing.md, 106-helm-charts.md

## Sources
- "Kubernetes Components" and "Controllers" (the reconciliation loop), Kubernetes documentation: https://kubernetes.io/docs/concepts/architecture/controller/
- "Deployments", Kubernetes documentation: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
