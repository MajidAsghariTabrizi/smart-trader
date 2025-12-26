# 🏗️ SmartTrader SaaS Foundation — Implementation Plan

## 📋 Overview

This plan implements a **staging-first, additive-only** SaaS foundation for SmartTrader:
- Auth system (JWT, users)
- Plans system (FREE/PRO/PROFESSIONAL)
- Market data provider interface
- Behavior intelligence engine
- New frontend pages
- New API endpoints

**All changes are backward-compatible and staging-safe.**

---

## 🗄️ Database Schema Changes

### New Tables (CREATE TABLE only)

#### `users`
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'USER',  -- USER | ADMIN
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### `user_plans`
```sql
CREATE TABLE IF NOT EXISTS user_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT NOT NULL,  -- FREE | PRO | PROFESSIONAL
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### `insights_posts`
```sql
CREATE TABLE IF NOT EXISTS insights_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    sentiment TEXT,  -- POSITIVE | NEGATIVE | NEUTRAL
    key_points TEXT,  -- JSON array
    author_id INTEGER,
    is_published INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,
    FOREIGN KEY (author_id) REFERENCES users(id)
);
```

**Migration Strategy**: Add to `database_setup.py` → `ensure_schema()` function.

---

## 🔐 Auth Module (`auth.py`)

### Dependencies
- `python-jose[cryptography]` for JWT
- `passlib[bcrypt]` for password hashing
- `python-multipart` for form data

### Functions
- `hash_password(password: str) -> str`
- `verify_password(plain: str, hashed: str) -> bool`
- `create_access_token(data: dict) -> str`
- `get_current_user(token: str) -> Optional[dict]`

### FastAPI Dependencies
- `get_current_user_dep() -> Depends` → Returns user dict or raises 401
- `require_auth()` → Decorator/Depends wrapper
- `require_plan(plan: str)` → Checks user plan

---

## 📦 Plans Module (`plans.py`)

### Functions
- `get_user_plan(user_id: int) -> Optional[dict]` → Returns active plan
- `assign_default_plan(user_id: int) -> bool` → Assigns FREE on register
- `set_user_plan(user_id: int, plan: str, duration_days: int = None) -> bool`
- `require_plan(plan: str)` → FastAPI Depends for plan checks

### Plan Hierarchy
- `FREE` < `PRO` < `PROFESSIONAL`
- Users with higher plans can access lower-tier features

---

## 🌐 Market Data Provider Interface (`market_providers.py`)

### Provider Interface
```python
class MarketDataProvider:
    def get_candles(symbol: str, tf: str, limit: int) -> List[Dict]
    def get_ticker(symbol: str) -> Dict
    def normalize_candle(raw: Dict) -> Dict  # Returns {time, open, high, low, close, volume}
```

### Implementations
1. **WallexProvider** (existing `wallex_client.py` wrapper)
2. **CoinGeckoProvider** (new, fallback)
3. **CoinCapProvider** (new, second fallback)

### Unified Fetcher
- `get_market_data(symbol: str, tf: str, limit: int, provider: str = None) -> List[Dict]`
- Config-driven selection: `MARKET_DATA_PROVIDER` env var
- Automatic fallback on failure

---

## 🧠 Behavior Intelligence Engine (`behavior_engine.py`)

### Functions
- `compute_volume_spike_score(volume_history: List[float]) -> float` → [0..100]
- `compute_volatility_shift_score(atr_history: List[float]) -> float` → [0..100]
- `compute_momentum_burst_score(price_history: List[float]) -> float` → [0..100]
- `compute_behavior_score(symbol: str, market_data: List[Dict]) -> Dict`:
  ```python
  {
      "behavior_score": 0..100,
      "volume_spike_score": 0..100,
      "volatility_shift_score": 0..100,
      "momentum_burst_score": 0..100,
      "explanations": [
          "Volume increased 2.3x above average",
          "ATR expansion indicates high volatility",
          ...
      ]
  }
  ```

**Note**: No on-chain data in Phase 1. Only market proxies.

---

## 🚀 New API Endpoints (web_app.py)

### Auth Endpoints
- `POST /api/auth/register` → `{email, password}` → `{user_id, token}`
- `POST /api/auth/login` → `{email, password}` → `{token, user}`
- `GET /api/auth/me` → (auth required) → `{user, plan}`

### Insights Endpoints (Public)
- `GET /api/insights/feed?limit=20` → List of published insights
- `GET /api/insights/latest` → Latest highlights + sentiment summary

### Market Endpoints (Public)
- `GET /api/market/overview?symbol=BTC` → Normalized market metrics
- `GET /api/market/behavior?symbol=BTC` → Behavior score + explanations

### App Endpoints (Auth Required)
- `GET /api/app/me/summary` → User plan, symbols, alert status, etc.

### Admin Endpoints (Admin Only)
- `POST /api/admin/users/{user_id}/plan` → `{plan, duration_days}` → Set user plan

**⚠️ All existing endpoints remain unchanged.**

---

## 🎨 Frontend Pages (static/)

### New Pages
1. **Landing** (`/` or `/landing.html`)
   - Public hero section
   - Features overview
   - CTA to register/login

2. **Login** (`/login.html`)
   - Email/password form
   - Redirect to `/app` on success

3. **Register** (`/register.html`)
   - Email/password form
   - Auto-assigns FREE plan

4. **Pricing** (`/pricing.html`)
   - FREE/PRO/PROFESSIONAL tiers
   - Feature comparison

5. **Insights** (`/insights.html`)
   - Public news/analysis feed
   - Fetches from `/api/insights/feed`

6. **App Dashboard** (`/app.html`)
   - Authenticated user dashboard
   - Market intelligence
   - Bot decisions
   - Whale behavior proxies
   - Plan-specific features

### JavaScript
- `static/js/auth.js` → Login/register logic, token storage
- `static/js/app.js` → App dashboard logic (new, separate from existing)

### CSS
- Minimal additions to `style.css` for new pages
- RTL-friendly, responsive

---

## 📁 File Structure

```
smart-trader-stg/
├── auth.py                    # NEW: Auth module
├── plans.py                   # NEW: Plans module
├── market_providers.py        # NEW: Provider interface
├── behavior_engine.py          # NEW: Behavior intelligence
├── web_app.py                 # MODIFIED: Add new endpoints
├── database_setup.py           # MODIFIED: Add new tables
├── requirements.txt           # MODIFIED: Add deps
├── static/
│   ├── landing.html           # NEW
│   ├── login.html             # NEW
│   ├── register.html          # NEW
│   ├── pricing.html           # NEW
│   ├── insights.html          # NEW
│   ├── app.html               # NEW
│   ├── js/
│   │   ├── auth.js            # NEW
│   │   ├── app.js             # NEW (app dashboard)
│   │   └── home.js            # UNCHANGED
│   └── css/
│       └── style.css          # MODIFIED: Add styles
└── CURRENT_STATE_MAP.md      # NEW: Documentation
```

---

## ✅ Implementation Order

1. ✅ Database schema (migrations)
2. ✅ Auth module (`auth.py`)
3. ✅ Plans module (`plans.py`)
4. ✅ Auth endpoints (`POST /api/auth/*`, `GET /api/auth/me`)
5. ✅ Market provider interface
6. ✅ Behavior engine
7. ✅ New market/insights endpoints
8. ✅ Frontend pages (landing, login, register, pricing, insights, app)
9. ✅ Admin endpoint
10. ✅ Testing checklist

---

## 🧪 Testing Checklist

### Backend (curl)
```bash
# Health check
curl http://localhost:8100/api/health

# Register
curl -X POST http://localhost:8100/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Login
curl -X POST http://localhost:8100/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Get me (with token)
curl http://localhost:8100/api/auth/me \
  -H "Authorization: Bearer <token>"

# Market overview
curl http://localhost:8100/api/market/overview?symbol=BTC

# Behavior
curl http://localhost:8100/api/market/behavior?symbol=BTC

# Insights feed
curl http://localhost:8100/api/insights/feed

# App summary (auth required)
curl http://localhost:8100/api/app/me/summary \
  -H "Authorization: Bearer <token>"
```

### Frontend (Browser)
- [ ] Landing page loads
- [ ] Login form works
- [ ] Register creates user + FREE plan
- [ ] Pricing page displays tiers
- [ ] Insights page shows feed
- [ ] App dashboard requires auth
- [ ] App dashboard shows market data + behavior

---

## 🔒 Security Notes

- Passwords: bcrypt hashing (12 rounds)
- JWT: 24h expiration, HS256
- CORS: Already configured (allow all)
- SQL injection: Use parameterized queries (already done)
- Rate limiting: Consider adding (future)

---

## 🚦 Staging-First Strategy

1. All changes target **staging** first
2. Test on `stg.quantiviq.xyz`
3. Verify no production impact
4. Merge to production after validation

---

## 📝 Next: Start Implementation

Ready to proceed with step-by-step implementation.

