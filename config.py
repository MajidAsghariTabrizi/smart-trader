import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "y", "on")


ENV = os.getenv("ENV", "prod")

SYMBOL = os.getenv("SYMBOL", "BTCTMN")
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "TMN")

MIN_TRADE_VALUE = int(os.getenv("MIN_TRADE_VALUE", "100000"))
MIN_ORDER_QTY = float(os.getenv("MIN_ORDER_QTY", "0"))
MIN_NOTIONAL = float(os.getenv("MIN_NOTIONAL", "0"))

PRIMARY_TF = os.getenv("PRIMARY_TF", "240")
CONFIRM_TF = os.getenv("CONFIRM_TF", "60")

MAX_CANDLES_PRIMARY = int(os.getenv("MAX_CANDLES_PRIMARY", "2200"))
MAX_CANDLES_CONFIRM = int(os.getenv("MAX_CANDLES_CONFIRM", "600"))

ALLOW_INTRACANDLE = _get_bool("ALLOW_INTRACANDLE", "true")
LIVE_POLL_SECONDS = int(os.getenv("LIVE_POLL_SECONDS", "12"))

STRATEGY = {
    "weights": {
        "trend": float(os.getenv("W_TREND", "0.30")),
        "momentum": float(os.getenv("W_MOMENTUM", "0.20")),
        "meanrev": float(os.getenv("W_MEANREV", "0.15")),
        "breakout": float(os.getenv("W_BREAKOUT", "0.20")),
        "behavior": float(os.getenv("W_BEHAVIOR", "0.15")),
    },

    "s_buy": float(os.getenv("S_BUY", "0.18")),
    "s_sell": float(os.getenv("S_SELL", "0.18")),

    "min_adx_for_trend": float(os.getenv("MIN_ADX_FOR_TREND", "18.0")),
    "require_mtf_agreement": _get_bool("REQUIRE_MTF_AGREEMENT", "true"),

    # 🔥 این نسخه دقیقاً همان چیزی است که trading_logic نیاز دارد
    "regime_scale": {
        "LOW": float(os.getenv("REGIME_SCALE_LOW", "0.7")),
        "NEUTRAL": float(os.getenv("REGIME_SCALE_NEUTRAL", "1.0")),
        "HIGH": float(os.getenv("REGIME_SCALE_HIGH", "1.3")),
    },

    "allow_intracandle": _get_bool("ALLOW_INTRACANDLE", "true"),
    "decision_buffer": float(os.getenv("DECISION_BUFFER", "0.00")),
    "mtf_confirm_bar": float(os.getenv("MTF_CONFIRM_BAR", "0.18")),

    # Volatility best-practice guards
    "min_vr_trade": float(os.getenv("MIN_VR_TRADE", "0.88")),
    "min_vr_intracandle": float(os.getenv("MIN_VR_INTRACANDLE", "0.95")),
    "vr_adapt_k": float(os.getenv("VR_ADAPT_K", "0.25")),
    "vr_adapt_clamp": float(os.getenv("VR_ADAPT_CLAMP", "0.08")),
    "impulse_only_high": _get_bool("IMPULSE_ONLY_HIGH", "true"),

    "atr_stop_mult": float(os.getenv("ATR_STOP_MULT", "2.0")),
    "max_risk_per_trade": float(os.getenv("RISK_PER_TRADE", "0.01")),
}

TELEGRAM = {
    "enabled": _get_bool("TELEGRAM_ENABLED", "true"),
    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
    "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
    "min_level": os.getenv("TELEGRAM_MIN_LEVEL", "INFO"),
}

WALLEX = {
    "base_url": os.getenv("WALLEX_BASE_URL", "https://api.wallex.ir"),
    "api_key": os.getenv("WALLEX_API_KEY"),
    "timeout": int(os.getenv("WALLEX_TIMEOUT", "10")),
    "retries": int(os.getenv("WALLEX_RETRIES", "3")),
    "rate_limit_per_sec": float(os.getenv("WALLEX_RATE_LIMIT_PER_SEC", "4")),
}

START_EQUITY = float(os.getenv("START_EQUITY", "100000000.0"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "smart_trader.log")
LOG_DIR = os.getenv("LOG_DIR", "")

DATABASE_PATH = os.getenv("DATABASE_PATH", "trading_data.db")
