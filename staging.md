# 📘 SmartTrader — STAGING CONTEXT (0 → 100)

## 1️⃣ هدف STAGING
STAGING برای توسعه‌های آینده، تغییرات اساسی و آماده‌سازی SaaS ساخته شده است، بدون ایجاد ریسک برای Production.

اهداف اصلی:
- mirror رفتار production بدون تداخل
- دیتابیس جدا و ایزوله
- CI/CD مستقل
- رفتار امن و آهسته (مناسب تست)
- بستر اجرای فازهای SaaS

---
nano /etc/nginx/sites-enabled/smarttrader-stg

## 2️⃣ دامنه‌ها
| Environment | Domain |
|------------|--------|
| Production | quantiviq.xyz |
| Staging | stg.quantiviq.xyz |

---

## 3️⃣ ساختار سرور
```
/root/
 ├─ smart-trader/          # PROD
 │   ├─ venv/
 │   ├─ trading_data.db
 │   └─ code
 │
 └─ smart-trader-stg/      # STAGING
     ├─ venv/
     ├─ trading_data_stg.db
     ├─ static/            # UI (home.html)
     └─ code
```

> هیچ فایل یا دیتابیسی بین prod و stg share نیست.

---

## 4️⃣ دیتابیس (Database Isolation)

پشتیبانی از override مسیر دیتابیس با متغیر محیطی:
```
SMARTTRADER_DB_PATH
```

در STAGING:
```
/root/smart-trader-stg/trading_data_stg.db
```

API و Bot هر دو از این مسیر استفاده می‌کنند.

---

## 5️⃣ سرویس‌های systemd

### API (STAGING)
- Service: smarttrader-api-stg
- Port داخلی: 127.0.0.1:8100
- Reverse Proxy با Nginx

### Bot (STAGING)
- Service: smarttrader-bot-stg
- تنظیمات کلیدی:
```
ENV=staging
LIVE_POLL_SECONDS=3600
```

Bot فقط هر ۱ ساعت دیتا fetch می‌کند.

---

## 6️⃣ Nginx Configuration (STAGING)

```
server_name stg.quantiviq.xyz;

root /root/smart-trader-stg/static;
index home.html;

location / {
    try_files $uri /home.html;
}

location /api/ {
    proxy_pass http://127.0.0.1:8100/;
}
```

- `/` → UI استیج
- `/api/*` → API استیج

---

## 7️⃣ حذف پروژه Docs

- حذف DNS مربوط به docs-market
- غیرفعال‌سازی nginx site مربوطه
- حذف CI/CD و دامنه وابسته

در حال حاضر هیچ پروژه‌ای با SmartTrader تداخل ندارد.

---

## 8️⃣ CI/CD Strategy

### Branch Strategy
| Branch | Deploy Target |
|------|--------------|
| main | Production |
| staging | STAGING |

### Workflow STAGING
- File: .github/workflows/deploy-stg.yml
- Trigger: push به branch staging
- SSH به سرور
- اجرای deploy-stg.sh
- restart services
- health check

---

## 9️⃣ deploy-stg.sh (STAGING)

ویژگی‌ها:
- safe git reset
- فعال‌سازی venv
- نصب dependency
- restart service
- health check

Script تمیز و بدون diff-marker است.

---

## 🔐 امنیت

- SSH Key جدا برای CI
- Secret: SMARTTRADER_STG_SSH_KEY
- هیچ کلید production در STAGING استفاده نمی‌شود

---

## 🔟 رفتار Bot (Prod vs Staging)

| Feature | Prod | Staging |
|-------|------|---------|
| Polling | realtime | هر ۱ ساعت |
| DB | shared | جدا |
| Risk | واقعی | ایزوله |
| SaaS Dev | ❌ | ✅ |

---

## 1️⃣1️⃣ وضعیت فعلی STAGING

- UI فعال
- API سالم (/api/health)
- دیتابیس جدا
- CI/CD پایدار
- Bot آهسته و امن

---

## 1️⃣2️⃣ آماده برای فازهای SaaS

STAGING آماده اجرای فازهای زیر است:
- PHASE 0 — SaaS Prep
- PHASE 1 — Auth & Users
- PHASE 2 — Pricing
- PHASE 3 — Multi-symbol
- PHASE 5 — Managed AutoTrade

---

## ✅ جمع‌بندی

STAGING یک محیط production-grade، ایمن و قابل توسعه است که تمام تغییرات ریسک‌دار ابتدا در آن انجام می‌شود و سپس به Production merge خواهد شد.

