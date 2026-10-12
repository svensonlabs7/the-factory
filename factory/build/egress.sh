#!/usr/bin/env bash
# Lock the build sandbox's network down before every run, and prove it. Exits non-zero (so no run starts) unless a
# container on the sandbox network cannot reach the internet directly. Idempotent: Colima drops iptables on restart.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)  # must be under the home folder: Colima shares only that with its VM
net=factory-sandbox subnet=172.30.0.0/24 proxy_ip=172.30.0.2
alpine=alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
curl=curlimages/curl@sha256:d9b4541e214bcd85196d6e92e2753ac6d0ea699f0af5741f8c6cccbfcf00ef4b

docker network inspect "$net" >/dev/null 2>&1 || docker network create --subnet "$subnet" "$net" >/dev/null

# Recreate the proxy only when its config changed, so a run does not reinstall it every time.
hash=$(cat "$here/egress/tinyproxy.conf" "$here/egress/allow" | shasum -a 256 | cut -c1-16)
if [ "$(docker inspect -f '{{.State.Running}} {{index .Config.Labels "factory.egress"}}' factory-egress 2>/dev/null)" != "true $hash" ]; then
  docker rm -f factory-egress >/dev/null 2>&1 || true
  docker run -d --name factory-egress --restart unless-stopped --label "factory.egress=$hash" \
    --network "$net" --ip "$proxy_ip" \
    -v "$here/egress/tinyproxy.conf:/etc/tinyproxy/tinyproxy.conf:ro" -v "$here/egress/allow:/etc/tinyproxy/allow:ro" \
    "$alpine" sh -c 'apk add --no-cache -q tinyproxy && exec tinyproxy -d -c /etc/tinyproxy/tinyproxy.conf' >/dev/null
fi

# Only the proxy may leave the subnet. Everything else from it is dropped, except replies on open connections.
colima ssh -- sudo sh -euc "
iptables -N FACTORY-EGRESS 2>/dev/null || true
iptables -F FACTORY-EGRESS
iptables -A FACTORY-EGRESS -s $proxy_ip/32 -j RETURN
iptables -A FACTORY-EGRESS -s $subnet -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
iptables -A FACTORY-EGRESS -s $subnet -d $subnet -j RETURN
iptables -A FACTORY-EGRESS -s $subnet -j DROP
iptables -C DOCKER-USER -j FACTORY-EGRESS 2>/dev/null || iptables -I DOCKER-USER 1 -j FACTORY-EGRESS"

# Prove it: a direct connection must fail, and the proxy must answer for an allowed host.
if docker run --rm --network "$net" "$curl" -s -m 5 -o /dev/null https://example.com; then
  echo "egress: the sandbox network reached the internet directly" >&2; exit 1
fi
for _ in 1 2 3 4 5 6 7 8 9 10; do
  code=$(docker run --rm --network "$net" "$curl" -s -m 8 -o /dev/null -w '%{http_code}' -x "http://$proxy_ip:8888" https://api.anthropic.com/v1/models || true)
  [ "$code" = 401 ] && exit 0
  sleep 2
done
echo "egress: the proxy is not passing api.anthropic.com (last code: ${code:-none})" >&2; exit 1
