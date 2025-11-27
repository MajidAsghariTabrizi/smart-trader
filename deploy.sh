#!/bin/bash
set -e

echo "📥 Pull latest code"
cd /root/smart-trader
git fetch origin main
git reset --hard origin/main

echo "🛠  Sync static files"
rm -rf /root/smart-trader/static/*
cp -r static/* /root/smart-trader/static/

echo "🚀 Restart backend"
systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service

echo "🔃 Reload nginx"
systemctl reload nginx
