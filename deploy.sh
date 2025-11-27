#!/bin/bash
set -euo pipefail

############################################
# SMARTTRADER DEPLOY v5 — Advanced Edition #
############################################

PROJECT_DIR="/root/smart-trader"
VENV_DIR="$PROJECT_DIR/venv"
BACKUP_DIR="$PROJECT_DIR/.rollback"
API_HEALTH_URL="http://127.0.0.1:8000/health"   # Customize if needed

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
    ok "No changes found — deployment skipped."
    exit 0
fi

warn "Changes detected → Deployment starting."


############################################
# 3) Create rollback point
############################################
step "Creating rollback point..."

rm -rf "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/smarttrader_backup.tar.gz" \
    --exclude=venv \
    --exclude=__pycache__ \
    --exclude=.pytest_cache \
    .

ok "Rollback snapshot created."


############################################
# 4) Pull new code
############################################
step "Pulling latest code..."
git reset --hard origin/main
ok "Repository updated."


############################################
# 5) Load .env (if exists)
############################################
step "Loading environment variables..."

if [[ -f ".env" ]]; then
    export $(grep -v '^#' .env | xargs)
    ok ".env loaded."
else
    warn ".env not found (skipping)."
fi


############################################
# 6) Create/Activate virtual environment
############################################
step "Ensuring virtual environment..."

if [[ ! -d "$VENV_DIR" ]]; then
    warn "venv not found → creating..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
ok "venv activated."


############################################
# 7) Install dependencies safely
############################################
step "Installing/upgrading dependencies..."

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --upgrade

if ! pip check; then
    err "Dependency conflict detected! Rolling back..."
    tar -xzf "$BACKUP_DIR/smarttrader_backup.tar.gz" -C .
    exit 1
fi

ok "Dependencies installed successfully."

############################################
# 8) Clean Python caches
############################################
step "Cleaning Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} +
ok "Cache cleaned."


############################################
# 9) Restart services gracefully
############################################
step "Restarting API and Bot services..."

systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

ok "Services restarted."


############################################
# 10) Health Check (API must respond)
############################################
step "Running API health check..."

sleep 3
if curl -s --max-time 3 "$API_HEALTH_URL" | grep -q "ok"; then
    ok "API is healthy."
else
    err "API health check failed!"

    warn "Rolling back to previous version..."
    tar -xzf "$BACKUP_DIR/smarttrader_backup.tar.gz" -C .

    systemctl restart smarttrader-api.service
    systemctl restart smarttrader-bot.service

    err "Rollback completed due to failed deploy."
    exit 1
fi


############################################
# 11) Reload Nginx
############################################
step "Reloading Nginx..."
systemctl reload nginx
ok "Nginx reloaded."


############################################
# 12) Done
############################################
ok "🎉 Deployment completed successfully!"
exit 0
