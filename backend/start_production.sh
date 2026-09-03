#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${BACKEND_DIR}/venv/bin/python3"

if [[ ! -x "${PYTHON}" ]]; then
    echo "[FinanceDashboard] Python virtual environment not found: ${PYTHON}" >&2
    echo "Create it and install backend/requirements.txt before starting the service." >&2
    exit 1
fi

cd "${BACKEND_DIR}"
exec "${PYTHON}" -m uvicorn main:app \
    --host "${FD_HOST:-127.0.0.1}" \
    --port "${FD_PORT:-8010}"