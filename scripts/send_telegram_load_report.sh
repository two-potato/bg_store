#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: send_telegram_load_report.sh <summary_report.txt>"
  exit 1
fi

REPORT_PATH="$(realpath "$1")"
if [ ! -f "$REPORT_PATH" ]; then
  echo "Report file not found: $REPORT_PATH"
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/bot/.env.notify"
if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  exit 3
fi

BOT_TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -n1 | cut -d'=' -f2-)"
CHAT_ID="$(grep -E '^MANAGERS_GROUP_ID=' "$ENV_FILE" | head -n1 | cut -d'=' -f2-)"
if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
  echo "TELEGRAM_BOT_TOKEN or MANAGERS_GROUP_ID missing in $ENV_FILE"
  exit 4
fi

TEXT="$(cat "$REPORT_PATH")"

curl -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  --data-urlencode "text=${TEXT}" \
  -d "parse_mode=HTML" >/dev/null

curl -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendDocument" \
  -F "chat_id=${CHAT_ID}" \
  -F "caption=Отчёт Locust staircase (multi-session)" \
  -F "document=@${REPORT_PATH}" >/dev/null

echo "Telegram report sent to chat ${CHAT_ID}"
