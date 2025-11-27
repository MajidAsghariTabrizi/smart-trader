#!/bin/bash
set -e

GREEN="\e[32m"
YELLOW="\e[33m"
RED="\e[31m"
NC="\e[0m"

echo -e "${YELLOW}🔍 Checking for updates...${NC}"
git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}✅ No changes detected — skipping restart.${NC}"
    exit 0
fi

echo -e "${YELLOW}⬇ Pulling latest code...${NC}"
git pull origin main

echo -e "${YELLOW}📁 Sync static files...${NC}"
mkdir -p static
mkdir -p /root/smart-trader/static
cp -r static/* /root/smart-trader/static/ || true

echo -e "${YELLOW}📦 Updating dependencies...${NC}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo -e "${YELLOW}⚙ Creating virtual environment...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
fi

pip install --upgrade pip
pip install -r requirements.txt

echo -e "${YELLOW}🧹 Clearing Python cache...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} +

echo -e "${YELLOW}🚀 Restarting services...${NC}"
systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

echo -e "${GREEN}🎉 Deployment successful!${NC}"
