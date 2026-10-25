# 7. Docker

Track: K. Infrastructure · Status: proven · Updated: 2026-10-19

Triggers: files `(^|/)Dockerfile|\.dockerignore$|(^|/)compose\.ya?ml$` · lines `docker (run|build|pull|create)|DockerWorkspace|SERVER_IMAGE|--restart|platform=|^\s*FROM `

## What it is
Docker packages an application and its dependencies into an **image** — a stack of read-only **layers**, one per build instruction — and runs it as a **container**, an isolated process using Linux namespaces (its own view of processes, network, mounts) and cgroups (CPU/memory limits). Unlike a VM, containers share the host kernel, so they start in milliseconds and are light. An image is built from a `Dockerfile`; each instruction adds a layer, and Docker **caches** layers: on rebuild it reuses a layer if that instruction and everything it depends on are unchanged, and rebuilds from the first changed instruction onward. Images are identified by a tag (mutable) or a content-addressed **digest** (`sha256:…`, immutable). A container writes to a thin writable layer on top that is lost when it is removed, so persistent data lives in **volumes** or bind mounts. The isolation is strong but not a security boundary as hard as a VM: the shared kernel is the attack surface.

## When it is worth it
- Worth it when you need a **reproducible environment** independent of the host: pinned dependencies, the same image in CI and production, process isolation for untrusted or multi-tenant work, and easy teardown. It is the default unit of deployment for most server software now.
- Over-engineering when a tiny script with no awkward dependencies runs fine on the host and will only ever run there: the image build, registry and runtime add moving parts. Containerising a one-file cron job "for consistency" is usually not worth it. And a container is **not** a strong sandbox for hostile code on its own — if isolation is the goal, a VM boundary (the factory uses one) matters.

## How it fails
- **Cache-busting layer order:** copying fast-changing source *before* the slow dependency-install layer makes every source change rebuild the dependencies from scratch (proof: 2.3 s vs 0.1 s). The fix is to copy the dependency manifest and install first, then copy source.
- **Mutable tags drift:** depending on a tag like `:latest` means the image silently changes under you; two builds get different code. Pin by digest (108-dependency-hell.md).
- **Fat images:** build tools, caches and secrets left in layers bloat the image and leak data — a deleted file in a later layer still exists in the earlier one. Multi-stage builds and `.dockerignore` fix it.
- **Ephemeral writable layer mistaken for storage:** data written inside the container is lost on removal because it was not on a volume.
- **Host/arch assumptions:** an image built for one architecture will not run on another without the right `platform`; mounts and networking differ between Docker Desktop, a VM and native Linux.
- **Treating a container as a security sandbox:** running untrusted code in a plain container trusts the shared kernel; a kernel escape reaches the host (080-ssrf.md: the factory adds a VM and network lockdown precisely because a container alone is not enough).

## Review checklist
- [ ] **Is the Dockerfile ordered cheapest-stable-first?** · Applies when: the diff adds or reorders `COPY`/`RUN` in a Dockerfile with an expensive dependency step. · Block if: fast-changing files are copied before the dependency install, so ordinary changes bust the install cache.
- [ ] **Are base images and dependencies pinned immutably?** · Applies when: the diff references a base image or installs packages. · Block if: it depends on a mutable tag (`:latest` or a floating tag) where a digest or locked version is needed for reproducibility.
- [ ] **Is persistent data on a volume, not the container layer?** · Applies when: the diff has a container write data that must survive restarts. · Block if: the data is written to the container's writable layer with no volume/bind mount.
- [ ] **Is a container relied on as a security boundary for untrusted code?** · Applies when: the diff runs untrusted or multi-tenant code in a container. · Block if: isolation rests on the container alone, with no stronger boundary (VM, locked-down network, dropped capabilities) for the threat.

## In the factory
Docker is central and used carefully:
- **The build sandbox is a container, pinned by digest.** `run_agent.py:24` sets `SERVER_IMAGE = ghcr.io/openhands/agent-server@sha256:0823…` — immutable, so a run cannot drift onto a new image. It sets `platform="linux/arm64"` explicitly (the host is an M4; the arch pin is required — a memory of a past arm64 gotcha). Right.
- **The container is not trusted as the only boundary.** It runs inside a Colima VM and on a locked-down `factory-sandbox` network where direct egress is dropped and only an allowlisted proxy can leave (`egress.sh`, 080-ssrf.md, 097-dns.md). That is the card's "a container is not a security sandbox" rule applied correctly: the VM plus the network lock are the real boundary.
- **Volume and mount discipline:** the agent's workdir is bind-mounted (`run_agent.py:28` notes the VM mounts only the home directory, so the workdir must live under it). A known gotcha (memory): `/private/tmp` mounts are not shared into Colima, so a script had to be piped on stdin rather than `-v`-mounted.
- **The egress proxy is itself a container** (`alpine` running `tinyproxy`, `egress.sh`), recreated only when its config hash changes — a small layer-cache-like optimisation at the container level.
- Build-cache ordering (this card's proof) applies to the builder's uv environment and CI installs, already covered by 107-build-caching.md and 089-cold-starts.md.
- Not applicable at today's load: multi-stage image builds authored here (the agent-server image is upstream), a private registry, orchestration (8-kubernetes is next).

## Proof
`bash knowledge/systems/proofs/007_docker.sh`, real `docker build` on `alpine:3.20`, with the dependency install simulated by `sleep 2`; a unique source change each run so the cache cannot pre-hold it:
```
bad  : rebuild 2.3s, layers reused=0, install layer cached=NO
good : rebuild 0.1s, layers reused=2, install layer cached=yes
```
The `bad` Dockerfile copies source before the install, so a source change invalidates the install layer and it re-runs (2.3 s). The `good` Dockerfile copies the dependency manifest and installs first, then copies source, so the same source change reuses the cached install (0.1 s). Identical result on a second run.

## Related
108-dependency-hell.md, 107-build-caching.md, 089-cold-starts.md, 080-ssrf.md, 090-serverless-limits.md, 104-infrastructure-as-code.md

## Sources
- "Docker build cache" and "Dockerfile best practices", Docker documentation: https://docs.docker.com/build/cache/
- "Overview of containers / images and layers", Docker documentation: https://docs.docker.com/get-started/docker-concepts/building-images/understanding-image-layers/
