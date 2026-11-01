#!/usr/bin/env bash
# Start the local stack without changing the existing Docker volume namespace.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

for command in docker pnpm; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Missing %s. Install it before starting the project.\n' "$command" >&2
    exit 1
  fi
done
if ! docker info >/dev/null 2>&1; then
  printf 'Start Docker Desktop (or the Docker daemon), then run this command again.\n' >&2
  exit 1
fi
if [[ ! -d frontend/node_modules ]]; then
  pnpm --dir frontend install --frozen-lockfile
fi

# The repository was renamed; retain the original project name and data volumes.
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://127.0.0.1:5173,http://localhost:5175,http://127.0.0.1:5175}"
# Refresh mounts after Docker/WSL restarts to avoid stale API/worker storage views.
docker compose -p file-intake-processing-service up --build --force-recreate -d --wait
printf '\nDashboard: http://localhost:5175\nCtrl+C stops the frontend; Docker services keep running.\n\n'
exec pnpm --dir frontend dev --host 127.0.0.1 --port 5175 --strictPort
