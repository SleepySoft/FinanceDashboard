#!/bin/bash
# FinanceDashboard - start backend (8000) + frontend dev server in background
cd "$(dirname "$0")"

FRONTEND_PORT="${1:-80}"

echo "[FinanceDashboard] Starting backend and frontend ..."
echo

# Backend
nohup ./backend/start.sh > /tmp/fin-backend.log 2>&1 &
echo "  Backend  -> http://localhost:8000  (log: /tmp/fin-backend.log)"

sleep 3

# Frontend
nohup ./start-frontend.sh dev "$FRONTEND_PORT" > /tmp/fin-frontend.log 2>&1 &
echo "  Frontend -> http://localhost:$FRONTEND_PORT  (log: /tmp/fin-frontend.log)"

echo
echo "Services started in background. Use ./stop_all.sh to stop them."
