#!/usr/bin/env bash
set -euo pipefail

MANAGER_ADDR="${MANAGER_ADDR:-}"
SWARM_WORKER_TOKEN="${SWARM_WORKER_TOKEN:-}"

if [[ -z "$MANAGER_ADDR" || -z "$SWARM_WORKER_TOKEN" ]]; then
  echo "MANAGER_ADDR and SWARM_WORKER_TOKEN are required" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed" >&2
  exit 2
fi

state="$(docker info --format '{{.Swarm.LocalNodeState}}')"
if [[ "$state" == "active" ]]; then
  echo "This node is already in a swarm; nothing to do."
  exit 0
fi

docker swarm join --token "$SWARM_WORKER_TOKEN" "$MANAGER_ADDR:2377"
echo "Worker joined swarm via $MANAGER_ADDR:2377"
