#!/usr/bin/env bash
set -euo pipefail

MANAGER_ADDR="${MANAGER_ADDR:-192.168.0.4}"
WORKER_ADDR="${WORKER_ADDR:-192.168.0.5}"
APP_DIR="${APP_DIR:-/opt/servio/current}"
SHARED_DIR="${SHARED_DIR:-/opt/servio/shared}"
BACKUP_DIR="${BACKUP_DIR:-/opt/servio/backups/postgres}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed" >&2
  exit 2
fi

if ! ip -4 addr show | grep -Fq "$MANAGER_ADDR/"; then
  echo "Manager address $MANAGER_ADDR is not assigned to this host" >&2
  ip -4 -br addr >&2
  exit 2
fi

if ! docker info >/dev/null 2>&1; then
  echo "Current user cannot access Docker. Add the deploy user to the docker group and re-login." >&2
  exit 2
fi

swarm_state="$(docker info --format '{{.Swarm.LocalNodeState}}')"
if [[ "$swarm_state" == "inactive" ]]; then
  docker swarm init --advertise-addr "$MANAGER_ADDR" --listen-addr "$MANAGER_ADDR:2377"
elif [[ "$(docker info --format '{{.Swarm.ControlAvailable}}')" != "true" ]]; then
  echo "This node is already in a swarm but is not a manager" >&2
  exit 2
fi

manager_node_id="$(docker info --format '{{.Swarm.NodeID}}')"
docker node update --label-add servio.role=core "$manager_node_id" >/dev/null

mkdir -p \
  "$APP_DIR/.deploy" \
  "$SHARED_DIR/letsencrypt" \
  "$SHARED_DIR/letsencrypt-lib" \
  "$SHARED_DIR/certbot-www" \
  "$BACKUP_DIR"

for volume in servio_pgdata servio_redisdata servio_opensearchdata servio_staticfiles servio_media; do
  docker volume inspect "$volume" >/dev/null 2>&1 || docker volume create "$volume" >/dev/null
done

worker_node_id=""
while IFS= read -r node_id; do
  [[ -z "$node_id" ]] && continue
  addr="$(docker node inspect "$node_id" --format '{{.Status.Addr}}' 2>/dev/null || true)"
  if [[ "$addr" == "$WORKER_ADDR" ]]; then
    worker_node_id="$node_id"
    break
  fi
done < <(docker node ls -q)

if [[ -n "$worker_node_id" ]]; then
  worker_state="$(docker node inspect "$worker_node_id" --format '{{.Status.State}}')"
  if [[ "$worker_state" != "ready" ]]; then
    echo "Worker $WORKER_ADDR is present but not Ready (state=$worker_state)" >&2
    exit 1
  fi
  docker node update --label-add servio.role=worker "$worker_node_id" >/dev/null
  echo "Worker $WORKER_ADDR is Ready and labeled servio.role=worker"
else
  echo "Worker $WORKER_ADDR has not joined yet. Join it, then rerun this script to apply its label."
fi

echo
echo "Cluster nodes:"
docker node ls
echo
echo "Worker join command:"
docker swarm join-token worker
