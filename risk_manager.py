from logger import get_logger

logger = get_logger()

# Gold / XAUUSD: 1 pip ≈ $0.10 per 0.01 lot (micro), contract = 100 oz
# For most forex pairs: 1 pip = 0.0001, 10 USD per pip per standard lot
# For XAUUSD: 1 pip = 0.01 (2-decimal pricing), $1 per pip per standard lot

DEFAULT_SL_PIPS = 50          # used when SL is absent for forex pairs
DEFAULT_SL_POINTS_GOLD = 500  # XAUUSD points (= 50 pips at 2-decimal)
MAX_LOT = 1.0
MIN_LOT = 0.01


def _is_gold(symbol: str) -> bool:
    return symbol.upper() in ("XAUUSD", "GOLD", "XAUEUR")


def calculate_lot(
    symbol: str,
    entry: float,
    sl: float | None,
    risk_percent: float,
    balance: float,
) -> float:
    """
    Calculate lot size so that the risk equals risk_percent of balance.
    Falls back to DEFAULT_LOT when insufficient data.
    """
    if balance <= 0 or risk_percent <= 0:
        logger.warning("Invalid balance or risk_percent — using min lot")
        return MIN_LOT

    risk_amount = balance * (risk_percent / 100.0)

    if sl is None or entry is None or entry == 0:
        logger.warning(f"SL not provided for {symbol} — using default pip distance")
        if _is_gold(symbol):
            sl_distance_points = DEFAULT_SL_POINTS_GOLD
            # XAUUSD: 1 standard lot = 100 oz, pip value ≈ $1/pip at 2-decimal
            pip_value_per_lot = 1.0
            sl_pips = sl_distance_points / 10.0
        else:
            sl_pips = DEFAULT_SL_PIPS
            pip_value_per_lot = 10.0  # USD per pip, standard lot, USD account
    else:
        diff = abs(entry - sl)
        if _is_gold(symbol):
            # Gold quoted in 2 decimal places; 0.01 = 1 pip
            sl_pips = diff / 0.01
            pip_value_per_lot = 1.0
        else:
            # Forex: 0.0001 = 1 pip (handles JPY pairs too via rough estimate)
            pip_size = 0.01 if "JPY" in symbol.upper() else 0.0001
            sl_pips = diff / pip_size
            pip_value_per_lot = 10.0

    if sl_pips <= 0:
        logger.warning("SL pips calculated as zero — using min lot")
        return MIN_LOT

    lot = risk_amount / (sl_pips * pip_value_per_lot)
    lot = round(max(MIN_LOT, min(MAX_LOT, lot)), 2)

    logger.info(
        f"Risk calc: balance={balance:.2f}, risk={risk_percent}%, "
        f"sl_pips={sl_pips:.1f}, lot={lot}"
    )
    return lot
