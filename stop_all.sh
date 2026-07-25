#!/bin/bash
# FinanceDashboard - stop backend (uvicorn) and frontend (vite)
cd "$(dirname "$0")"

echo "[FinanceDashboard] Stopping backend and frontend ..."
echo

STOPPED=0

# Backend: uvicorn main:app
PIDS=$(pgrep -f "uvicorn main:app" || true)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | while read -r pid; do
        echo "  Stopping backend (PID $pid)"
        kill "$pid" 2>/dev/null
    done
    STOPPED=1
fi

# Frontend: vite dev server under this project
PIDS=$(pgrep -f "FinanceDashboard.*vite|vite.*FinanceDashboard" || true)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | while read -r pid; do
        echo "  Stopping frontend (PID $pid)"
        kill "$pid" 2>/dev/null
    done
    STOPPED=1
fi

if [ "$STOPPED" -eq 0 ]; then
    echo "  No running services found."
fi

echo
echo "Done."
