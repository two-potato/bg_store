#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-servio}"
HEALTH_URL="${HEALTH_URL:-https://24sparts.ru/health/}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-360}"
POLL_SECONDS="${POLL_SECONDS:-5}"
REQUIRE_MONITORING="${REQUIRE_MONITORING:-1}"

required_services=(backend frontend celery-worker celery-beat bot bot-notify search-api recommendation-api db redis opensearch nginx)
if [[ "$REQUIRE_MONITORING" == "1" ]]; then
  required_services+=(prometheus alertmanager grafana node-exporter cadvisor)
fi
start_ts="$(date +%s)"

print_diagnostics() {
  docker stack services "$STACK_NAME" >&2 || true
  docker stack ps "$STACK_NAME" --no-trunc >&2 || true
  for service in backend search-api recommendation-api db redis opensearch nginx; do
    container="$(docker ps --filter "label=com.docker.swarm.service.name=${STACK_NAME}_${service}" --format '{{.ID}}' | head -n1)"
    if [[ -n "$container" ]]; then
      echo "--- ${STACK_NAME}_${service} logs ---" >&2
      docker logs --tail 80 "$container" >&2 || true
    fi
  done
}

service_ready() {
  local service="$1"
  local line replicas current desired
  line="$(docker service ls --filter "name=${STACK_NAME}_${service}" --format '{{.Name}} {{.Replicas}}' | head -n1)"
  [[ -n "$line" ]] || return 1
  replicas="${line##* }"
  current="${replicas%/*}"
  desired="${replicas#*/}"
  [[ "$desired" != "0" && "$current" == "$desired" ]]
}

local_container_healthy() {
  local service="$1"
  local container status
  container="$(docker ps --filter "label=com.docker.swarm.service.name=${STACK_NAME}_${service}" --format '{{.ID}}' | head -n1)"
  [[ -n "$container" ]] || return 1
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
  [[ "$status" == "healthy" || "$status" == "running" ]]
}

while true; do
  all_ready=1
  for service in "${required_services[@]}"; do
    if ! service_ready "$service"; then
      all_ready=0
      break
    fi
  done

  if [[ "$all_ready" == "1" ]]; then
    core_healthy=1
    for service in backend search-api recommendation-api db redis opensearch nginx; do
      if ! local_container_healthy "$service"; then
        core_healthy=0
        break
      fi
    done
    if [[ "$core_healthy" == "1" ]]; then
      break
    fi
  fi

  now="$(date +%s)"
  if (( now - start_ts >= TIMEOUT_SECONDS )); then
    echo "Swarm services did not converge and become healthy within ${TIMEOUT_SECONDS}s" >&2
    print_diagnostics
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

for _ in $(seq 1 30); do
  if curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null; then
    echo "Application readiness OK: $HEALTH_URL"
    docker stack services "$STACK_NAME"
    exit 0
  fi
  sleep 3
done

echo "Public Django readiness check failed: $HEALTH_URL" >&2
print_diagnostics
exit 1
