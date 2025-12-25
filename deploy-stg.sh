#!/bin/bash
set -euo pipefail

PROJECT_DIR="/root/smart-trader-stg"
VENV_DIR="$PROJECT_DIR/venv"
API_URL="http://127.0.0.1:8100/api/health"

cd "$PROJECT_DIR"

echo "▶ Fetching staging branch..."
git fetch origin staging
git reset --hard origin/staging

echo "▶ Activating venv..."
source "$VENV_DIR/bin/activate"

echo "▶ Installing dependencies..."
pip install -r requirements.txt >/dev/null 2>&1

echo "▶ Restarting STAGING services..."
systemctl restart smarttrader-api-stg
systemctl restart smarttrader-bot-stg

sleep 2

echo "▶ Health check..."
curl -fs "$API_URL" | grep -q ok

echo "✅ STAGING deploy successful"
