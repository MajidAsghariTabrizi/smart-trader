#!/bin/bash

set -e

cd /root/smart-trader

echo "🟦 Pull latest"
git fetch origin main
git reset --hard origin/main

echo "🟨 Build frontend"
cd frontend
npm install
npm run build

echo "🟧 Sync static"
rm -rf /root/smart-trader/static/*
cp -r dist/* /root/smart-trader/static/

cd /root/smart-trader

echo "🟩 Restart API"
systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

echo "🟪 Reload nginx"
systemctl reload nginx
