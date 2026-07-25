#!/bin/bash
# FinanceDashboard - restart all services
cd "$(dirname "$0")"

echo "[FinanceDashboard] Restarting services ..."
echo

./stop_all.sh

echo
echo "Starting services again ..."
./start_all.sh
