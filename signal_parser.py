import re
import unicodedata
from typing import Optional

from logger import get_logger, log_section

logger = get_logger()

# Regex patterns
_RE_HEADER = re.compile(
    r"(XAUUSD|EURUSD|GBPUSD|USDJPY|AUDUSD|USDCAD|USDCHF|NZDUSD|GOLD)"
    r"\s*(BUY|SELL)[.\s]*"
    r"([\d.]+)",
    re.IGNORECASE,
)
_RE_TP = re.compile(r"\bTP[.\s]*([\d.]+)", re.IGNORECASE)
_RE_SL = re.compile(r"\bSL?[.\s]*([\d.]+)", re.IGNORECASE)

# Phrases that mark a result/update message — not a new signal
_IGNORE_PHRASES = (
    "TP HIT", "TARGET COMPLETE", "PROFIT DONE", "PIPS PROFIT",
    "ALL TARGET", "PIPS DONE", "HIT TP", "CLOSED", "RUNNING",
)


def _normalize(text: str) -> str:
    """Convert bold Unicode letters/digits to plain ASCII."""
    return "".join(
        c if ord(c) < 128 else unicodedata.normalize("NFKC", c)
        for c in text
    )


def _is_result_update(text: str) -> bool:
    upper = text.upper()
    return any(phrase in upper for phrase in _IGNORE_PHRASES)


def parse_signal(raw_message: str) -> Optional[dict]:
    """
    Parse a raw Telegram message using regex.
    Returns a signal dict, or None on a hard failure.
    Always sets is_signal=True/False — never returns None for a parseable message.
    """
    log_section(logger, "SIGNAL RECEIVED", raw_message)

    text = _normalize(raw_message)

    # Fast-reject result/update messages
    if _is_result_update(text):
        result = {"symbol": None, "action": None, "entry": None,
                  "sl": None, "tp": None, "is_signal": False}
        log_section(logger, "PARSED RESULT", "Result update — ignored")
        return result

    header = _RE_HEADER.search(text)
    if not header:
        result = {"symbol": None, "action": None, "entry": None,
                  "sl": None, "tp": None, "is_signal": False}
        log_section(logger, "PARSED RESULT", "No trade signal found")
        return result

    symbol = header.group(1).upper()
    if symbol == "GOLD":
        symbol = "XAUUSD"
    action = header.group(2).upper()
    entry = float(header.group(3))

    tps = [float(m) for m in _RE_TP.findall(text)]
    sl_match = _RE_SL.search(text)
    sl = float(sl_match.group(1)) if sl_match else None

    signal = {
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "sl": sl,
        "tp": tps if tps else None,
        "is_signal": True,
    }

    import json
    log_section(logger, "PARSED RESULT", json.dumps(signal, indent=2))
    return signal
