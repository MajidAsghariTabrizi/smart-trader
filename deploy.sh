#!/bin/bash
set -e

echo "➡ Pull last code"
git fetch origin main
git reset --hard origin/main

echo "➡ Sync static"
rm -rf /root/smart-trader/static/*
cp -r static/* /root/smart-trader/static/

echo "➡ Update dependencies"
source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt --quiet

echo "➡ Restart services"
systemctl restart smarttrader-api
systemctl restart smarttrader-bot
systemctl reload nginx

echo "✅ Finished"
