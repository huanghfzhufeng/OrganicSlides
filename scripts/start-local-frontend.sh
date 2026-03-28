#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-15173}"
BACKEND_PORT="${BACKEND_PORT:-18000}"

cd "${ROOT_DIR}/frontend"
export FRONTEND_HOST
export FRONTEND_PORT
export VITE_API_URL="${VITE_API_URL:-http://127.0.0.1:${BACKEND_PORT}/api/v1}"

exec npm run dev
