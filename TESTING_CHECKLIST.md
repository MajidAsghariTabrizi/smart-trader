# 🧪 SmartTrader SaaS Foundation — Testing Checklist

## ✅ Backend API Tests (curl)

### Health Check
```bash
curl http://localhost:8100/api/health
# Expected: {"status": "ok", "db_path": "...", "tables": [...]}
```

### Auth: Register
```bash
curl -X POST http://localhost:8100/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123456"}'

# Expected: {"user_id": 1, "token": "...", "email": "test@example.com"}
```

### Auth: Login
```bash
curl -X POST http://localhost:8100/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123456"}'

# Expected: {"token": "...", "user": {...}, "plan": "FREE"}
```

### Auth: Get Me (with token)
```bash
TOKEN="<token from login>"
curl http://localhost:8100/api/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Expected: {"user": {...}, "plan": "FREE"}
```

### Market: Overview
```bash
curl http://localhost:8100/api/market/overview?symbol=BTC

# Expected: {"symbol": "BTC", "price": ..., "price_change_24h": ..., ...}
```

### Market: Behavior
```bash
curl http://localhost:8100/api/market/behavior?symbol=BTC

# Expected: {"behavior_score": 0..100, "volume_spike_score": ..., "explanations": [...]}
```

### Insights: Feed
```bash
curl http://localhost:8100/api/insights/feed?limit=10

# Expected: [] (empty if no insights posted yet)
```

### Insights: Latest
```bash
curl http://localhost:8100/api/insights/latest

# Expected: {"highlights": [], "sentiment": "NEUTRAL", "key_points": []}
```

### App: Summary (auth required)
```bash
TOKEN="<token>"
curl http://localhost:8100/api/app/me/summary \
  -H "Authorization: Bearer $TOKEN"

# Expected: {"user_id": 1, "email": "...", "plan": "FREE", ...}
```

### Admin: Set Plan (admin required)
```bash
# First, create admin user manually in DB or via script
TOKEN="<admin_token>"
curl -X POST http://localhost:8100/api/admin/users/1/plan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan": "PRO", "duration_days": 30}'

# Expected: {"user_id": 1, "plan": "PRO", "status": "updated"}
```

---

## 🌐 Frontend Tests (Browser)

### Landing Page
- [ ] Navigate to `/` or `/landing.html`
- [ ] Verify hero section displays
- [ ] Click "ثبت‌نام رایگان" → redirects to `/register.html`
- [ ] Click "ورود" → redirects to `/login.html`

### Register Page
- [ ] Navigate to `/register.html`
- [ ] Enter email and password (min 6 chars)
- [ ] Submit form
- [ ] Verify redirect to `/app.html` after successful registration
- [ ] Check localStorage has `token`

### Login Page
- [ ] Navigate to `/login.html`
- [ ] Enter registered email/password
- [ ] Submit form
- [ ] Verify redirect to `/app.html`
- [ ] Test invalid credentials → error message displays

### Pricing Page
- [ ] Navigate to `/pricing.html`
- [ ] Verify all 3 plans display (FREE, PRO, PROFESSIONAL)
- [ ] Verify feature lists are correct
- [ ] Click CTA buttons → redirects to `/register.html`

### Insights Page
- [ ] Navigate to `/insights.html`
- [ ] Verify page loads (may be empty if no insights)
- [ ] Check API call to `/api/insights/feed`

### App Dashboard
- [ ] Navigate to `/app.html` (must be logged in)
- [ ] If not logged in → redirects to `/login.html`
- [ ] Verify user email and plan display in header
- [ ] Verify "وضعیت حساب" card loads
- [ ] Verify "رفتار بازار" card shows behavior score
- [ ] Verify "نظرات بازار" card shows market overview
- [ ] Verify "آخرین تصمیم‌های ربات" section loads
- [ ] Check auto-refresh every 30 seconds

---

## 🗄️ Database Tests

### Verify Tables Created
```sql
sqlite3 trading_data_stg.db
.tables
# Should show: users, user_plans, insights_posts (plus existing tables)
```

### Verify User Created
```sql
SELECT * FROM users WHERE email = 'test@example.com';
# Should show user with hashed password
```

### Verify Plan Assigned
```sql
SELECT * FROM user_plans WHERE user_id = 1;
# Should show FREE plan, is_active = 1
```

---

## 🔒 Security Tests

- [ ] Register with duplicate email → error 400
- [ ] Login with wrong password → error 401
- [ ] Access `/api/auth/me` without token → error 401
- [ ] Access `/api/app/me/summary` without token → error 401
- [ ] Access `/api/admin/users/1/plan` as non-admin → error 403
- [ ] JWT token expires after 24h (test manually)

---

## 🚀 Integration Tests

### Full User Flow
1. [ ] Register new user
2. [ ] Verify FREE plan assigned
3. [ ] Login with credentials
4. [ ] Access app dashboard
5. [ ] View market behavior data
6. [ ] View recent decisions

### Market Data Fallback
1. [ ] Disable Wallex (simulate failure)
2. [ ] Request `/api/market/overview?symbol=BTC`
3. [ ] Verify fallback to CoinGecko/CoinCap works

---

## 📝 Notes

- All existing endpoints (`/api/prices`, `/api/decisions`, etc.) must continue working
- Database migrations are additive only (no data loss)
- Staging environment: `stg.quantiviq.xyz` (port 8100)
- Production environment: `quantiviq.xyz` (port 8000) — **DO NOT TEST ON PRODUCTION**

---

## ✅ Completion Criteria

- [ ] All backend endpoints return expected responses
- [ ] All frontend pages load and function correctly
- [ ] Auth flow works end-to-end
- [ ] Database tables created successfully
- [ ] No existing functionality broken
- [ ] No linting errors
- [ ] Ready for staging deployment

