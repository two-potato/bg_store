#!/usr/bin/env bash
set -euo pipefail

BASE_REF="${BASE_REF:-}"
ALLOW_RISKY_MIGRATIONS="${ALLOW_RISKY_MIGRATIONS:-0}"

if [[ -z "$BASE_REF" ]]; then
  echo "BASE_REF is required" >&2
  exit 2
fi

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  echo "Migration safety base ref not found: $BASE_REF" >&2
  exit 2
fi

mapfile -t migration_files < <(git diff --name-only "$BASE_REF"..HEAD -- 'backend/*/migrations/*.py' | grep -v '/__init__\.py$' || true)
if (( ${#migration_files[@]} == 0 )); then
  echo "No changed Django migrations since $BASE_REF"
  exit 0
fi

# Conservative gate for operations that commonly break code-only rollback.
# AlterField is intentionally not blanket-blocked because many safe index/default/nullability
# changes use it; reviewers still inspect `migrate --plan` before release.
risky_pattern='migrations\.(RemoveField|DeleteModel|RunSQL|RunPython|RenameField|RenameModel)[[:space:]]*\('
risky=0
for file in "${migration_files[@]}"; do
  [[ -f "$file" ]] || continue
  if grep -En "$risky_pattern" "$file"; then
    echo "Potentially rollback-sensitive migration: $file" >&2
    risky=1
  fi
done

if [[ "$risky" == "1" && "$ALLOW_RISKY_MIGRATIONS" != "1" ]]; then
  echo "Refusing deployment with rollback-sensitive migrations. Review for expand/contract compatibility and set ALLOW_RISKY_MIGRATIONS=1 only after explicit approval." >&2
  exit 1
fi

if [[ "$risky" == "1" ]]; then
  echo "WARNING: risky migration override is enabled"
else
  echo "Migration safety check passed for ${#migration_files[@]} changed migration file(s)"
fi
