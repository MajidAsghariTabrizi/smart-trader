#!/bin/bash
set -euo pipefail

############################################
# SMARTTRADER DEPLOY v5 — Clean & Advanced
############################################

PROJECT_DIR="/root/smart-trader"
VENV_DIR="$PROJECT_DIR/venv"
BACKUP_DIR="$PROJECT_DIR/.rollback"
API_HEALTH_URL="http://127.0.0.1:8000/api/health"   # or /health if exists

# --- COLORS ---
GREEN="\e[32m"
YELLOW="\e[33m"
RED="\e[31m"
CYAN="\e[36m"
NC="\e[0m"

step()  { echo -e "${CYAN}\n▶ $1 ${NC}"; }
ok()    { echo -e "${GREEN}✔ $1 ${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $1 ${NC}"; }
err()   { echo -e "${RED}✘ $1 ${NC}"; }

############################################
# 1) Go to project directory
############################################
step "Switching to project directory..."
cd "$PROJECT_DIR"

############################################
# 2) Fetch updates & skip if no change
############################################
step "Checking for new commits..."
git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [[ "$LOCAL" == "$REMOTE" ]]; then
    ok "No changes — deployment not required."
    exit 0
fi

warn "Changes detected → Deployment starting."

############################################
# 3) Create rollback point
############################################
step "Creating rollback backup..."

rm -rf "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/snapshot.tar.gz" \
    --exclude=venv \
    --exclude=__pycache__ \
    .

ok "Rollback snapshot saved."

############################################
# 4) Pull new code
############################################
step "Pulling latest code..."
git reset --hard origin/main
ok "Code updated."

############################################
# 5) Load .env
############################################
step "Loading environment variables..."

if [[ -f ".env" ]]; then
    export $(grep -v '^#' .env | xargs)
    ok ".env loaded."
else
    warn ".env not found — continuing."
fi

############################################
# 6) Ensure virtualenv
############################################
step "Checking Python virtual environment..."

if [[ ! -d "$VENV_DIR" ]]; then
    warn "Virtual env missing — creating..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
ok "Virtualenv activated."

############################################
# 7) Install dependencies
############################################
step "Upgrading dependencies..."

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --upgrade

pip check || true

ok "Dependencies updated."

############################################
# 8) Clean pycache
############################################
step "Cleaning Python caches..."
find . -type d -name "__pycache__" -exec rm -rf {} +
ok "Cache cleaned."

############################################
# 9) Restart services
############################################
step "Restarting SmartTrader services..."

systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

ok "Services restarted."

############################################
# 10) API Health Check
############################################
step "Checking API health..."

sleep 2

if curl -fs "$API_HEALTH_URL" | grep -q "ok"; then
    ok "API is healthy."
else
    err "API health FAILED!"
    warn "Rolling back..."

    tar -xzf "$BACKUP_DIR/snapshot.tar.gz" -C .

    systemctl restart smarttrader-api.service
    systemctl restart smarttrader-bot.service

    err "Rollback complete due to failed deploy."
    exit 1
fi

############################################
# 11) Reload nginx
############################################
step "Reloading NGINX..."
systemctl reload nginx
ok "NGINX reloaded."

############################################
# 12) Done
############################################
ok "🎉 Deployment completed successfully!"
exit 0
