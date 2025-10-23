#!/usr/bin/env bash
set -euo pipefail

# Rebuild and restart the AuditFairness dashboard to reflect latest UI changes
# Usage: bash scripts/rebuild_dashboard.sh

SERVICE=auditfairness

echo "[Rebuild] Building $SERVICE image without cache..."
docker compose build --no-cache "$SERVICE"

echo "[Rebuild] Restarting $SERVICE container..."
docker compose up -d "$SERVICE"

# Optional: show last few lines of logs to confirm startup
echo "[Rebuild] Tail logs (press Ctrl+C to stop)"
docker compose logs -f --tail=100 "$SERVICE"