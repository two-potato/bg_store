#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="${DEPLOY_DIR:-$ROOT_DIR/.deploy}"

if [[ ! -f "$DEPLOY_DIR/previous-sha" ]]; then
  echo "No previous deployment SHA recorded" >&2
  exit 2
fi
previous_sha="$(tr -d '[:space:]' < "$DEPLOY_DIR/previous-sha")"
if [[ -z "$previous_sha" ]]; then
  echo "Previous deployment SHA is empty" >&2
  exit 2
fi

cat >&2 <<'EOF'
Rollback is code-only: database migrations are NOT automatically reversed.
Production migrations must remain backward-compatible using expand/contract changes.
EOF

IMAGE_TAG="$previous_sha" SKIP_MIGRATIONS=1 "$ROOT_DIR/scripts/swarm_deploy.sh"
