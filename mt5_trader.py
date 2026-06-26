import time
from typing import Optional

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

import config
from logger import get_logger, log_section
from risk_manager import calculate_lot

logger = get_logger()


def _check_mt5() -> bool:
    if not MT5_AVAILABLE:
        logger.error("MetaTrader5 package not installed or not available on this OS.")
        return False
    return True


def initialize_mt5(retries: int = 3) -> bool:
    """Login to MT5 terminal with retry logic."""
    if not _check_mt5():
        return False

    for attempt in range(1, retries + 1):
        logger.info(f"MT5 init attempt {attempt}/{retries}...")
        if mt5.initialize(
            login=config.MT5_ACCOUNT,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        ):
            info = mt5.account_info()
            if info:
                logger.info(
                    f"MT5 connected — Account: {info.login}, "
                    f"Server: {info.server}, Balance: {info.balance:.2f} {info.currency}"
                )
                return True
        logger.warning(f"MT5 init failed (attempt {attempt}): {mt5.last_error()}")
        if attempt < retries:
            time.sleep(3)

    logger.error("MT5 initialization failed after all retries.")
    return False


def get_account_info() -> Optional[object]:
    if not _check_mt5():
        return None
    return mt5.account_info()


def get_price(symbol: str, action: str) -> Optional[float]:
    """Return ask price for BUY, bid for SELL."""
    if not _check_mt5():
        return None
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"Cannot get tick for {symbol}: {mt5.last_error()}")
        return None
    return tick.ask if action.upper() == "BUY" else tick.bid


def get_open_positions(symbol: Optional[str] = None) -> list:
    """Return open positions, optionally filtered by symbol."""
    if not _check_mt5():
        return []
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return list(positions) if positions else []


def move_sl_to_breakeven(tickets: list, entry: float) -> None:
    """Move SL to entry price (breakeven) for all still-open positions in tickets."""
    if not _check_mt5():
        return

    for ticket in tickets:
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            continue  # already closed

        pos = positions[0]
        sym_info = mt5.symbol_info(pos.symbol)
        digits = sym_info.digits if sym_info else 2
        be_price = round(entry, digits)

        if abs(pos.sl - be_price) < 10 ** -digits:
            continue  # SL already at breakeven

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": be_price,
            "tp": pos.tp,
        }

        if config.DRY_RUN:
            logger.info(f"[DRY RUN] Would move SL to breakeven {be_price} for ticket {ticket}")
            continue

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Breakeven SL set to {be_price} for ticket {ticket}")
        else:
            retcode = result.retcode if result else "None"
            comment = result.comment if result else mt5.last_error()
            logger.error(f"Failed to set breakeven for ticket {ticket}: retcode={retcode}, {comment}")


def _send_order(request: dict, label: str) -> Optional[int]:
    """Send a single order and return ticket number on success, None on failure."""
    result = mt5.order_send(request)
    if result is None:
        logger.error(f"{label} — order_send returned None: {mt5.last_error()}")
        return None
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"{label} — Order placed. Ticket: {result.order}")
        return result.order
    else:
        logger.error(f"{label} — Order failed. retcode: {result.retcode}, comment: {result.comment}")
        return None


def place_trade(signal: dict) -> tuple:
    """
    Execute one market order per TP level.
    Total lot is split evenly across all orders (min volume_min per order).
    Returns (success: bool, magic: int, tickets: list[int], entry: float).
    """
    symbol = signal.get("symbol")
    action = (signal.get("action") or "").upper()
    entry = signal.get("entry")
    sl = signal.get("sl")
    tp_list = signal.get("tp") or []

    if not symbol or action not in ("BUY", "SELL"):
        logger.warning(f"Invalid signal for trade execution: {signal}")
        return False, 0, [], 0.0

    if not _check_mt5():
        return False, 0, [], 0.0

    if not mt5.symbol_select(symbol, True):
        logger.error(f"Symbol {symbol} not found or not selectable.")
        return False, 0, [], 0.0

    info = mt5.account_info()
    if not info:
        logger.error("Cannot retrieve account info.")
        return False, 0, [], 0.0

    sym_info = mt5.symbol_info(symbol)
    if sym_info is None:
        logger.error(f"Cannot get symbol info for {symbol}")
        return False, 0, [], 0.0

    digits = sym_info.digits
    volume_step = sym_info.volume_step
    volume_min = sym_info.volume_min

    balance = info.balance
    total_lot = calculate_lot(symbol, entry, sl, config.RISK_PERCENT, balance)

    num_orders = max(len(tp_list), 1)
    raw_lot_each = total_lot / num_orders
    lot_each = max(volume_min, round(raw_lot_each - (raw_lot_each % volume_step), 2))

    price = get_price(symbol, action)
    if price is None:
        return False, 0, [], 0.0

    sl_price = round(float(sl), digits) if sl else 0.0
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    magic = int(time.time()) % 99_999_999
    orders = tp_list if tp_list else [None]

    log_section(
        logger,
        "TRADE EXECUTED" if not config.DRY_RUN else "DRY RUN — TRADE SKIPPED",
        (
            f"Symbol : {symbol}\n"
            f"Action : {action}\n"
            f"Orders : {num_orders} (one per TP)\n"
            f"Lot ea.: {lot_each}  (total: {round(lot_each * num_orders, 2)})\n"
            f"Price  : {price}\n"
            f"SL     : {sl_price}\n"
            f"TPs    : {tp_list}\n"
            f"Magic  : {magic}\n"
            f"Dry Run: {config.DRY_RUN}"
        ),
    )

    if config.DRY_RUN:
        logger.info("[DRY RUN] Orders not sent to MT5.")
        return True, magic, [], price

    tickets = []
    for i, tp in enumerate(orders):
        tp_price = round(float(tp), digits) if tp is not None else 0.0
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_each,
            "type": order_type,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 20,
            "magic": magic,
            "comment": f"TG-TP{i + 1}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        ticket = _send_order(request, f"Order {i + 1}/{num_orders} TP={tp_price}")
        if ticket:
            tickets.append(ticket)

    success = len(tickets) > 0
    logger.info(f"{len(tickets)}/{num_orders} orders placed successfully.")
    return success, magic, tickets, price if price else 0.0


def close_trade(symbol: str) -> bool:
    """Close all open positions for a given symbol."""
    if not _check_mt5():
        return False

    positions = get_open_positions(symbol)
    if not positions:
        logger.info(f"No open positions found for {symbol}.")
        return True

    success = True
    for pos in positions:
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = get_price(symbol, "SELL" if close_type == mt5.ORDER_TYPE_SELL else "BUY")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "TG-Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if config.DRY_RUN:
            logger.info(f"[DRY RUN] Would close ticket {pos.ticket} for {symbol}")
            continue

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Closed ticket {pos.ticket} for {symbol}")
        else:
            retcode = result.retcode if result else "None"
            comment = result.comment if result else mt5.last_error()
            logger.error(f"Failed to close {pos.ticket}: retcode={retcode}, {comment}")
            success = False

    return success
