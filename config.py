import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise ValueError(f"Missing required env variable: {key}")
    return val

def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (ValueError, TypeError):
        return default

def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")

# Telegram
TELEGRAM_API_ID: int = int(_require("TELEGRAM_API_ID"))
TELEGRAM_API_HASH: str = _require("TELEGRAM_API_HASH")
TELEGRAM_CHANNEL: str = _require("TELEGRAM_CHANNEL")  # set in .env — live or test

# Known channels (for reference / quick switching in .env)
CHANNEL_LIVE = "https://t.me/golLdsr"       # live signal source
CHANNEL_TEST = "https://t.me/brijesh_forex"  # test / paper-trade channel

# MT5
MT5_ACCOUNT: int = int(_require("MT5_ACCOUNT"))
MT5_PASSWORD: str = _require("MT5_PASSWORD")
MT5_SERVER: str = _require("MT5_SERVER")

# Risk
RISK_PERCENT: float = _float("RISK_PERCENT", 1.0)
DEFAULT_LOT: float = _float("DEFAULT_LOT", 0.1)

# Mode
DRY_RUN: bool = _bool("DRY_RUN", False)
