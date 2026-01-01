#!/bin/bash
PROJECT_DIR="/root/smart-trader-stg"
cd $PROJECT_DIR
git fetch origin staging
git reset --hard origin/staging
source venv/bin/activate
pip install -r requirements.txt
python3 -c "import database_setup; database_setup.ensure_schema()"
# ری‌استارت سرویس‌های استیجینگ
systemctl restart smarttrader-api-stg.service
systemctl restart smarttrader-bot-stg.service
echo "✅ STAGING Updated Successfully"