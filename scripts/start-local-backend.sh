#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-18000}"

if [[ ! -x "${ROOT_DIR}/.venv/bin/uvicorn" ]]; then
  echo ".venv 未就绪。先在项目根目录运行: python3 -m venv .venv && ./.venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

cd "${ROOT_DIR}/backend"
exec "${ROOT_DIR}/.venv/bin/uvicorn" main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" --reload
