#!/bin/bash

echo "🚀 SmartTrader Deploy Started"

cd ~/smart-trader || exit

echo "📥 Pull latest code"
git fetch origin main
git reset --hard origin/main

echo "🧹 Cleaning old static files"
rm -rf ~/smart-trader/static/*
mkdir -p ~/smart-trader/static/

echo "📦 Copy new static files"
cp -r frontend/dist/* ~/smart-trader/static/

echo "🔄 Restart backend"
systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

echo "🌐 Reload nginx"
systemctl reload nginx

echo "✅ Deploy completed successfully!"
