#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root (or with sudo)." >&2
    exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl is required." >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_DIR}/backend"
START_SCRIPT="${BACKEND_DIR}/start_production.sh"
SERVICE_NAME="${FD_SYSTEMD_SERVICE:-financedashboard}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
RUN_USER="$(stat -c '%U' "${PROJECT_DIR}")"
RUN_GROUP="$(stat -c '%G' "${PROJECT_DIR}")"
HOST="${FD_HOST:-127.0.0.1}"
PORT="${FD_PORT:-8010}"

if [[ ! "${SERVICE_NAME}" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
    echo "Invalid systemd service name: ${SERVICE_NAME}" >&2
    exit 1
fi

if [[ ! -x "${BACKEND_DIR}/venv/bin/python3" ]]; then
    echo "Backend virtual environment is missing: ${BACKEND_DIR}/venv" >&2
    exit 1
fi

chmod 0755 "${START_SCRIPT}"

cat >"${UNIT_PATH}" <<EOF
[Unit]
Description=FinanceDashboard FastAPI service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${BACKEND_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=FD_HOST=${HOST}
Environment=FD_PORT=${PORT}
EnvironmentFile=-${PROJECT_DIR}/.env
ExecStart=${START_SCRIPT}
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# Replace a legacy manually started development server from this checkout.
LEGACY_PATTERN="${BACKEND_DIR}/venv/bin/u[v]icorn main:app"
mapfile -t LEGACY_PIDS < <(pgrep -f "${LEGACY_PATTERN}" || true)
if (( ${#LEGACY_PIDS[@]} > 0 )); then
    echo "Stopping legacy Uvicorn process(es): ${LEGACY_PIDS[*]}"
    kill -TERM "${LEGACY_PIDS[@]}" 2>/dev/null || true
    for _ in {1..20}; do
        RUNNING=0
        for PID in "${LEGACY_PIDS[@]}"; do
            if kill -0 "${PID}" 2>/dev/null; then
                RUNNING=1
                break
            fi
        done
        (( RUNNING == 0 )) && break
        sleep 0.5
    done
    for PID in "${LEGACY_PIDS[@]}"; do
        kill -KILL "${PID}" 2>/dev/null || true
    done
fi

systemctl enable --now "${SERVICE_NAME}.service"

HEALTH_URL="http://${HOST}:${PORT}/api/auth/config"
for _ in {1..30}; do
    if curl --fail --silent --show-error --max-time 2 "${HEALTH_URL}" >/dev/null; then
        echo "FinanceDashboard is running: ${HEALTH_URL}"
        systemctl --no-pager --full status "${SERVICE_NAME}.service" | sed -n '1,12p'
        exit 0
    fi
    sleep 1
done

echo "Service failed its health check: ${HEALTH_URL}" >&2
systemctl --no-pager --full status "${SERVICE_NAME}.service" >&2 || true
journalctl -u "${SERVICE_NAME}.service" -n 50 --no-pager >&2 || true
exit 1