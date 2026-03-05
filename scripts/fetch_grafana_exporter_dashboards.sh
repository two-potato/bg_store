#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="deploy/grafana/dashboards"
mkdir -p "$OUT_DIR"

# slug:id
DASHBOARDS=(
  "node-exporter-full:1860"
  "cadvisor-exporter:14282"
  "postgres-exporter:9628"
  "redis-exporter:763"
  "nginx-exporter:12708"
  "elasticsearch-exporter:14191"
  "blackbox-exporter:7587"
)

for item in "${DASHBOARDS[@]}"; do
  slug="${item%%:*}"
  id="${item##*:}"
  out="$OUT_DIR/exporter_${slug}.json"
  echo "[dashboards] downloading id=$id -> $out"
  curl -fsSL "https://grafana.com/api/dashboards/${id}/revisions/latest/download" \
    | jq --arg uid "exporter-${slug}" --arg title "Exporter / ${slug}" '
        del(.__inputs)
        | .uid = $uid
        | .title = $title
        | (.. | strings) |= gsub("\\$\\{DS_[A-Za-z0-9_]+\\}"; "Prometheus")
        | (.. | objects | select(has("datasource")) | .datasource) |= (
            if type == "string" then
              if test("^\\$\\{DS_") then "Prometheus" else . end
            elif type == "object" then
              if has("uid") and (.uid|type=="string") and (.uid|test("^\\$\\{DS_")) then
                .uid = "prometheus" | .type = "prometheus"
              elif has("type") and .type == "prometheus" and (has("uid") | not) then
                . + {uid: "prometheus"}
              else
                .
              end
            else
              .
            end
          )
      ' > "$out"
done

echo "[dashboards] done"
