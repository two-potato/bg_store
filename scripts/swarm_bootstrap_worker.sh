#!/usr/bin/env bash
set -euo pipefail

MANAGER_ADDR="${MANAGER_ADDR:-192.168.0.4}"
WORKER_ADDR="${WORKER_ADDR:-192.168.0.5}"
SWARM_WORKER_TOKEN="${SWARM_WORKER_TOKEN:-}"

if [[ -z "$SWARM_WORKER_TOKEN" ]]; then
  echo "SWARM_WORKER_TOKEN is required" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed" >&2
  exit 2
fi
if ! ip -4 addr show | grep -Fq "$WORKER_ADDR/"; then
  echo "Worker address $WORKER_ADDR is not assigned to this host" >&2
  ip -4 -br addr >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "Current user cannot access Docker" >&2
  exit 2
fi

if command -v timeout >/dev/null 2>&1; then
  if ! timeout 3 bash -c "</dev/tcp/$MANAGER_ADDR/2377" 2>/dev/null; then
    echo "Cannot reach Swarm manager at $MANAGER_ADDR:2377 over the private network" >&2
    exit 1
  fi
fi

state="$(docker info --format '{{.Swarm.LocalNodeState}}')"
if [[ "$state" == "active" ]]; then
  echo "This node is already in a swarm; nothing to do."
  exit 0
fi

docker swarm join --advertise-addr "$WORKER_ADDR" --token "$SWARM_WORKER_TOKEN" "$MANAGER_ADDR:2377"
echo "Worker $WORKER_ADDR joined swarm via $MANAGER_ADDR:2377"
