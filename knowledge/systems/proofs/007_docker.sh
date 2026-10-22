#!/usr/bin/env bash
# Docker layer caching: instruction ORDER decides what the cache can reuse. A Dockerfile that copies source
# before the expensive dependency layer busts that layer on every source change; copying the dependency
# manifest first, installing, then copying source keeps the install cached. Real `docker build` on alpine;
# the "install" is `sleep 2` so the cache effect is visible without a network. Deterministic, no network.
set -euo pipefail
d=$(mktemp -d); trap 'rm -rf "$d"; docker rmi -f lc-bad lc-good >/dev/null 2>&1 || true' EXIT
mkdir -p "$d/bad" "$d/good"

cat > "$d/bad/Dockerfile" <<'EOF'
FROM alpine:3.20
COPY src.txt /src.txt
RUN sleep 2 && echo deps-installed > /deps
EOF
cat > "$d/good/Dockerfile" <<'EOF'
FROM alpine:3.20
COPY deps.txt /deps.txt
RUN sleep 2 && echo deps-installed > /deps
COPY src.txt /src.txt
EOF
nonce=$(date +%s%N)                                                # unique per run, so the cache cannot pre-hold it
echo "cold-$nonce" > "$d/bad/src.txt"; echo "cold-$nonce" > "$d/good/src.txt"; echo lib==1 > "$d/good/deps.txt"

DOCKER_BUILDKIT=0 docker build -t lc-bad "$d/bad" >/dev/null 2>&1   # cold builds prime the cache
DOCKER_BUILDKIT=0 docker build -t lc-good "$d/good" >/dev/null 2>&1

echo "changed-$nonce" > "$d/bad/src.txt"; echo "changed-$nonce" > "$d/good/src.txt"  # a never-seen source change, deps unchanged
for name in bad good; do
  start=$(python3 -c 'import time;print(time.time())')
  out=$(DOCKER_BUILDKIT=0 docker build -t lc-$name "$d/$name" 2>/dev/null)
  end=$(python3 -c 'import time;print(time.time())')
  reused=$(echo "$out" | grep -c 'Using cache' || true)
  install=$(echo "$out" | grep -A1 'sleep 2' | grep -cq 'Using cache' && echo yes || echo NO)
  dt=$(python3 -c "print(f'{$end-$start:.1f}')")
  printf '%-5s: rebuild %ss, layers reused=%s, install layer cached=%s\n' "$name" "$dt" "$reused" "$install"
done
