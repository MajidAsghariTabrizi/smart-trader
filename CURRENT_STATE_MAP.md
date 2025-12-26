# 📋 SmartTrader — Current State Map

## 🎯 Overview
SmartTrader is a live algorithmic trading system with:
- **Backend**: FastAPI (Python 3.12)
- **Trading Engine**: Continuous loop (main.py)
- **Database**: SQLite (file-based)
- **Frontend**: Static HTML + Vanilla JS + CSS
- **Deployment**: systemd services, nginx reverse proxy

---

## 🔌 Existing API Endpoints (web_app.py)

### Public Pages
- `GET /` → Returns `static/home.html`
- `GET /dashboard` → Returns `static/index.html`

### Public APIs
- `GET /api/health` → `{"status": "ok", "db_path": "...", "tables": [...]}`
- `GET /api/prices?limit=300` → Array of OHLCV candles from `trading_logs`
- `GET /api/decisions?limit=80` → Array of decision records from `trading_logs`
- `GET /api/btc_price` → `{"price": ..., "price_tmn": ..., "timestamp": ..., "history": [...]}`
- `GET /api/trades/recent?limit=50` → Array of closed trades from `trade_events`
- `GET /api/perf/summary` → `{"total_trades": ..., "wins": ..., "losses": ..., "winrate": ..., "total_pnl": ...}`
- `GET /api/perf/daily?limit=30` → Array of daily PnL records

**⚠️ CRITICAL**: All existing endpoints MUST remain unchanged.

---

## 🗄️ Database Schema (database_setup.py)

### Tables

#### `trading_logs`
- Main analysis log table
- Columns: `id`, `timestamp`, `price`, `open`, `high`, `low`, `volume`, `decision`, `regime`, `aggregate_s`, `adx`, `atr`, `reasons_json`, etc.
- Used by: `/api/prices`, `/api/decisions`

#### `trade_events`
- Trade lifecycle events (OPEN/CLOSE)
- Columns: `id`, `trade_id`, `timestamp`, `symbol`, `event_type`, `side`, `qty`, `entry_price`, `close_price`, `pnl`, `reason`
- Used by: `/api/trades/recent`, `/api/perf/summary`, `/api/perf/daily`

#### `account_state`
- Account snapshots
- Columns: `id`, `timestamp`, `symbol`, `equity`, `balance`, `position_side`, `position_qty`, `position_entry`, `position_stop`
- Used by: Performance calculations

**⚠️ CRITICAL**: No existing tables can be deleted or truncated.

---

## 📁 Frontend Structure

### Pages
- `static/home.html` → Landing page with ORB visualization
- `static/index.html` → Full dashboard

### JavaScript
- `static/js/home.js` → Main dashboard logic (1000+ lines)
  - Fetches from `/api/*` endpoints
  - Renders charts, heatmaps, decision lists
  - Updates every 10 seconds
- `static/js/app.js` → (Appears to be older/duplicate version)

### CSS
- `static/css/style.css` → Dark-Pro Neural Matrix theme

**⚠️ CRITICAL**: Existing pages must continue working.

---

## ⚙️ Trading Engine

### Core Files
- `main.py` → Main execution loop
  - Calls `wallex_client` for market data
  - Uses `trading_logic.SignalEngine` for decisions
  - Writes to `trading_logs`, `trade_events`, `account_state`
- `trading_logic.py` → Decision engine
  - `SignalEngine` class
  - `DecisionContext`, `StrategyParams`, `Account`, `Position`
- `wallex_client.py` → Market data client
  - `get_candles()`, `get_ticker()`
  - Uses Wallex UDF API

### Configuration
- `config.py` → Environment-based config
  - `ENV` (prod/staging)
  - `SYMBOL`, `WALLEX`, `STRATEGY`, `TELEGRAM`, etc.
- `database_setup.py` → DB schema management
  - `ensure_schema()` → Creates/migrates tables
  - `get_db_path()` → Supports `SMARTTRADER_DB_PATH` env var

**⚠️ CRITICAL**: Trading logic must not be modified unless explicitly requested.

---

## 🌐 Deployment

### Environments
- **Production**: `quantiviq.xyz` → `/root/smart-trader`
- **Staging**: `stg.quantiviq.xyz` → `/root/smart-trader-stg`

### Services
- `smarttrader-api.service` / `smarttrader-api-stg.service` → FastAPI (port 8000/8100)
- `smarttrader-bot.service` / `smarttrader-bot-stg.service` → Trading bot

### Nginx
- Production: `/api/*` → `http://127.0.0.1:8000`
- Staging: `/api/*` → `http://127.0.0.1:8100`
- Root: `try_files $uri /home.html`

**⚠️ CRITICAL**: Production nginx config must not change.

---

## ✅ Safe Extension Points

1. **New API endpoints** → Add to `web_app.py` (additive only)
2. **New database tables** → Add via `database_setup.py` (CREATE TABLE only)
3. **New frontend pages** → Add to `static/` (don't modify existing)
4. **New modules** → Create new `.py` files (don't refactor existing)

---

## 🚫 Forbidden Actions

1. ❌ Modify existing endpoint behavior/output
2. ❌ Delete/truncate existing tables
3. ❌ Change trading strategy logic
4. ❌ Modify production nginx/systemd
5. ❌ Refactor existing files
6. ❌ Introduce Docker/containers
7. ❌ Add frontend frameworks (React/Vue)

---

## 📝 Next Steps

Proceed with SaaS foundation implementation:
1. Auth system (users, JWT)
2. Plans system (FREE/PRO/PROFESSIONAL)
3. Market data expansion (provider interface)
4. Behavior intelligence (whale proxies)
5. New frontend pages
6. New API endpoints (additive only)

