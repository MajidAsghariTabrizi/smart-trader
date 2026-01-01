#!/bin/bash
PROJECT_DIR="/root/smart-trader"
cd $PROJECT_DIR
git fetch origin main
git reset --hard origin/main
source venv/bin/activate
pip install -r requirements.txt
# آپدیت دیتابیس (SaaS Tables)
python3 -c "import database_setup; database_setup.ensure_schema()"
# ری‌استارت سرویس‌های پروداکشن
systemctl restart smarttrader-api.service
systemctl restart smarttrader-bot.service
systemctl reload nginx
echo "✅ PRODUCTION Updated Successfully"