#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-servio}"
HEALTH_URL="${HEALTH_URL:-https://24sparts.ru/health/}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"
POLL_SECONDS="${POLL_SECONDS:-5}"

required_services=(backend frontend celery-worker celery-beat bot bot-notify db redis opensearch nginx)
start_ts="$(date +%s)"

service_ready() {
  local service="$1"
  local line desired current
  line="$(docker service ls --filter "name=${STACK_NAME}_${service}" --format '{{.Name}} {{.Replicas}}' | head -n1)"
  [[ -n "$line" ]] || return 1
  desired="${line##* }"
  current="${desired%/*}"
  desired="${desired#*/}"
  [[ "$desired" != "0" && "$current" == "$desired" ]]
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
    break
  fi

  now="$(date +%s)"
  if (( now - start_ts >= TIMEOUT_SECONDS )); then
    echo "Swarm services did not converge within ${TIMEOUT_SECONDS}s" >&2
    docker stack services "$STACK_NAME" >&2 || true
    docker stack ps "$STACK_NAME" --no-trunc >&2 || true
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

for _ in $(seq 1 20); do
  if curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null; then
    echo "Health check OK: $HEALTH_URL"
    docker stack services "$STACK_NAME"
    exit 0
  fi
  sleep 3
done

echo "HTTP health check failed: $HEALTH_URL" >&2
docker stack services "$STACK_NAME" >&2 || true
exit 1
