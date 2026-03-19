#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOCUST_BIN="${LOCUST_BIN:-$ROOT_DIR/.locust_env/bin/locust}"
HOST="${HOST:-https://potatofarm.ru}"
OUT_BASE="${OUT_BASE:-$ROOT_DIR/.artifacts/locust_runs}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$OUT_BASE/$STAMP"
mkdir -p "$RUN_DIR"

if [ ! -x "$LOCUST_BIN" ]; then
  echo "Locust not found at $LOCUST_BIN"
  exit 1
fi

run_session() {
  local name="$1"
  local users="$2"
  local spawn="$3"
  local step_users="$4"
  local step_time="$5"
  local stop_timeout="${6:-60}"

  local prefix="$RUN_DIR/$name"
  local step_seconds="${step_time%s}"
  local current=0
  local stages=""
  local total_runtime=0
  while [ "$current" -lt "$users" ]; do
    current=$((current + step_users))
    if [ "$current" -gt "$users" ]; then
      current="$users"
    fi
    if [ -n "$stages" ]; then
      stages="${stages};"
    fi
    stages="${stages}${current}x${step_seconds}"
    total_runtime=$((total_runtime + step_seconds))
  done
  total_runtime=$((total_runtime + stop_timeout + 30))
  echo ""
  echo "=== Session: $name | users=$users spawn=$spawn step_users=$step_users step_time=$step_time ==="
  STAIRCASE_STAGES="$stages" STAIRCASE_SPAWN_RATE="$spawn" "$LOCUST_BIN" \
    -f "$ROOT_DIR/scripts/locust_prod_staircase.py" \
    --headless \
    --host "$HOST" \
    --users "$users" \
    --spawn-rate "$spawn" \
    --stop-timeout "$stop_timeout" \
    --run-time "${total_runtime}s" \
    --only-summary \
    --csv "$prefix" \
    --html "$prefix.html"
}

# Session 1: baseline staircase
run_session "s01_baseline" 300 30 50 90s 60

# Session 2: stress staircase
run_session "s02_stress" 900 60 150 90s 90

# Session 3: peak staircase
run_session "s03_peak" 1200 80 200 90s 120

# Session 4: endurance staircase
run_session "s04_endurance" 800 50 200 120s 120

echo ""
echo "Load sessions completed. Artifacts: $RUN_DIR"
echo "$RUN_DIR"
