- PROJECT_DIR="/root/smart-trader"
+ PROJECT_DIR="/root/smart-trader-stg"

- API_URL="http://127.0.0.1:8000/api/health"
+ API_URL="http://127.0.0.1:8100/api/health"

- systemctl restart smarttrader-api.service
- systemctl restart smarttrader-bot.service
+ systemctl restart smarttrader-api-stg.service
+ systemctl restart smarttrader-bot-stg.service
