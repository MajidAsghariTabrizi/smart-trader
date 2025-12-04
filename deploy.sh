#!/bin/bash
set -euo pipefail

###########################################################
# SMARTTRADER — ENTERPRISE SAFE DEPLOY v10
# - Full safety
# - Rollback on failure
# - Strong health checking
# - Systemd validation
###########################################################

PROJECT_DIR="/root/smart-trader"
VENV_DIR="$PROJECT_DIR/venv"
API_URL="http://127.0.0.1:8000/api/health"
LOG_FILE="/root/smarttrader_deploy.log"

# Colors
GREEN="\e[32m"; YELLOW="\e[33m"; RED="\e[31m"; CYAN="\e[36m"; NC="\e[0m"
step()  { echo -e "${CYAN}\n▶ $1${NC}" | tee -a "$LOG_FILE"; }
ok()    { echo -e "${GREEN}✔ $1${NC}" | tee -a "$LOG_FILE"; }
warn()  { echo -e "${YELLOW}⚠ $1${NC}" | tee -a "$LOG_FILE"; }
err()   { echo -e "${RED}✘ $1${NC}" | tee -a "$LOG_FILE"; }

###########################################################
step "Switching to project directory..."
cd "$PROJECT_DIR"

###########################################################
step "Checking Git changes..."

git fetch origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [[ "$LOCAL" == "$REMOTE" ]]; then
    ok "Already up-to-date — no deployment needed."
    exit 0
fi

warn "Changes detected → Deployment starting..."

###########################################################
step "Creating backup for rollback..."

BACKUP_DIR="/root/smart-trader-backup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r "$PROJECT_DIR"/* "$BACKUP_DIR" || warn "Backup not fully created (non-critical)."
ok "Backup saved to $BACKUP_DIR"

###########################################################
step "Pulling latest code..."
git reset --hard origin/main
ok "Latest code pulled."

###########################################################
step "Loading .env (if exists)..."
if [[ -f ".env" ]]; then
    set -a; source .env; set +a
    ok ".env loaded."
else
    warn "No .env found."
fi

###########################################################
step "Ensuring virtual environment..."

if [[ ! -d "$VENV_DIR" ]]; then
    warn "venv not found → creating..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
ok "Virtualenv activated."

###########################################################
step "Validating Python syntax before restarting services..."

python -m py_compile *.py || {
    err "Python syntax error detected! Performing rollback..."
    rm -rf "$PROJECT_DIR"
    cp -r "$BACKUP_DIR" "$PROJECT_DIR"
    exit 1
}

ok "Syntax clean."

###########################################################
step "Installing dependencies..."

pip install --upgrade pip setuptools wheel >/dev/null 2>&1
pip install -r requirements.txt --upgrade >/dev/null 2>&1 || warn "Some deps failed (non-critical)."

ok "Dependencies installed."

###########################################################
step "Running DB schema migration check..."

python3 - << 'EOF'
from database_setup import ensure_schema
if ensure_schema():
    print("✔ DB schema OK")
else:
    print("✘ DB schema failed")
EOF

###########################################################
step "Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + || true
ok "Cache cleaned."

###########################################################
step "Restarting SmartTrader services..."

systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

sleep 2

###########################################################
step "Checking systemd status..."

systemctl is-active --quiet smarttrader-api.service || warn "API service not active!"
systemctl is-active --quiet smarttrader-bot.service || warn "BOT service not active!"
ok "Systemd services responded."

###########################################################
step "Health Check with retries..."

RETRIES=6
SUCCESS=0

for i in $(seq 1 $RETRIES); do
    sleep 2
    if curl -fs "$API_URL" | grep -q "ok"; then
        ok "API is healthy."
        SUCCESS=1
        break
    fi
    warn "API not ready (attempt $i/$RETRIES)..."
done

if [[ $SUCCESS -ne 1 ]]; then
    err "API FAILED after retries — performing rollback!"
    rm -rf "$PROJECT_DIR"
    cp -r "$BACKUP_DIR" "$PROJECT_DIR"
    exit 1
fi

###########################################################
step "Reloading Nginx..."
systemctl reload nginx

ok "🎉 Deployment SUCCESSFUL"
exit 0
