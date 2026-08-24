#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_FILE="${CRON_FILE:-/etc/cron.d/servio-swarm-backup}"
RUN_USER="${RUN_USER:-sergey}"
BACKUP_TIME="${BACKUP_TIME:-10 2 * * *}"
LOG_FILE="${LOG_FILE:-/var/log/servio-swarm-backup.log}"

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root to install $CRON_FILE" >&2
  exit 2
fi

backup_script="$ROOT_DIR/scripts/swarm_backup_postgres.sh"
if [[ ! -f "$backup_script" ]]; then
  echo "Backup script missing: $backup_script" >&2
  exit 2
fi
chmod +x "$backup_script"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
$BACKUP_TIME $RUN_USER cd $ROOT_DIR && $backup_script >> $LOG_FILE 2>&1
EOF
chmod 0644 "$CRON_FILE"

echo "Installed daily Swarm PostgreSQL backup cron at $CRON_FILE"
cat "$CRON_FILE"
