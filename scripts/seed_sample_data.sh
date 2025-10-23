#!/usr/bin/env bash
set -euo pipefail

# Seed sample data into PostgreSQL prediction_results for local testing
# Usage:
#   bash scripts/seed_sample_data.sh
# Prereqs:
#   - docker compose stack is up (postgres service running)
#   - file scripts/seed_sample_data.sql exists

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
SQL_FILE="$ROOT_DIR/scripts/seed_sample_data.sql"

if [[ ! -f "$SQL_FILE" ]]; then
  echo "[ERROR] SQL file not found: $SQL_FILE" >&2
  exit 1
fi

# Wait for postgres to be ready (simple retry loop)
echo "[INFO] Waiting for postgres to be ready..."
for i in {1..20}; do
  if docker compose exec -T postgres pg_isready -U healthflow -d healthflow >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ $i -eq 20 ]]; then
    echo "[ERROR] Postgres is not ready after waiting." >&2
    exit 1
  fi
done

echo "[INFO] Seeding sample data into prediction_results..."
cat "$SQL_FILE" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U healthflow -d healthflow >/dev/null

echo "[OK] Sample data seeded. Verify with:\n  docker compose exec postgres psql -U healthflow -d healthflow -c \"SELECT patient_pseudo_id, risk_score, prediction_timestamp FROM prediction_results ORDER BY prediction_timestamp DESC LIMIT 10;\""