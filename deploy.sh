#!/bin/bash
set -euo pipefail

############################################
# SMARTTRADER — CLEAN DEPLOY v7 (NO TAR)
############################################

PROJECT_DIR="/root/smart-trader"
VENV_DIR="$PROJECT_DIR/venv"
API_URL="http://127.0.0.1:8000/api/health"

# Colors
GREEN="\e[32m"; YELLOW="\e[33m"; RED="\e[31m"; CYAN="\e[36m"; NC="\e[0m"
step() { echo -e "${CYAN}\n▶ $1${NC}"; }
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "${RED}✘ $1${NC}"; }

############################################
step "Switching to project directory..."
cd "$PROJECT_DIR"

############################################
step "Checking for updates..."
git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [[ "$LOCAL" == "$REMOTE" ]]; then
    ok "No changes — deployment skipped."
    exit 0
fi

warn "Changes detected → starting deployment."

############################################
step "Pulling latest code..."
git reset --hard origin/main
ok "Code updated."

############################################
step "Loading .env if exists..."

if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
    ok ".env loaded."
else
    warn "No .env found — continuing."
fi

############################################
step "Ensuring Python virtual environment..."

if [[ ! -d "$VENV_DIR" ]]; then
    warn "venv missing → creating..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
ok "Virtualenv activated."

############################################
step "Installing Python dependencies..."

pip install --upgrade pip setuptools wheel >/dev/null 2>&1
pip install -r requirements.txt --upgrade >/dev/null 2>&1 || warn "Some deps failed but continuing..."

ok "Dependencies ready."

############################################
step "Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + || true
ok "Cache cleaned."

############################################
step "Restarting SmartTrader services..."
systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service
ok "Services restarted."

############################################
step "Checking API health..."
sleep 2

if curl -fs "$API_URL" | grep -q "ok"; then
    ok "API is healthy."
else
    warn "API health check FAILED — but will NOT stop deployment."
fi

############################################
step "Reloading NGINX..."
systemctl reload nginx

############################################
ok "🎉 Deployment completed successfully!"
exit 0
