#!/bin/bash

echo "🚀 SmartTrader Deploy Started"

cd /root/smart-trader || exit

echo "📥 Pull latest code"
git fetch origin main
git reset --hard origin/main

echo "🧹 Clean static/"
rm -rf /root/smart-trader/static/*
mkdir -p /root/smart-trader/static/

echo "📦 Build frontend"
cd frontend
npm install
npm run build

echo "📦 Copy new build → static/"
cp -r dist/* /root/smart-trader/static/

cd /root/smart-trader

echo "🔄 Restart backend"
systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

echo "🌐 Reload nginx"
systemctl reload nginx

echo "✅ Deploy completed successfully!"
