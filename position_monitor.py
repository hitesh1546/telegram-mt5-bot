import asyncio
from dataclasses import dataclass

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from logger import get_logger
from mt5_trader import move_sl_to_breakeven

logger = get_logger()

POLL_INTERVAL = 10  # seconds


@dataclass
class SignalGroup:
    magic: int
    entry: float
    tickets: list
    initial_count: int
    breakeven_triggered: bool = False


# In-memory registry: magic -> SignalGroup
_groups: dict = {}


def track_signal(magic: int, entry: float, tickets: list) -> None:
    """Register a new signal group for breakeven monitoring."""
    if not tickets:
        return
    _groups[magic] = SignalGroup(
        magic=magic,
        entry=entry,
        tickets=list(tickets),
        initial_count=len(tickets),
    )
    logger.info(f"Tracking {len(tickets)} order(s) for breakeven monitor (magic={magic}, entry={entry})")


def _get_open_tickets(tickets: list) -> list:
    """Return subset of tickets that are still open positions in MT5."""
    if not MT5_AVAILABLE:
        return tickets
    open_tickets = []
    for ticket in tickets:
        positions = mt5.positions_get(ticket=ticket)
        if positions:
            open_tickets.append(ticket)
    return open_tickets


async def monitor_loop() -> None:
    """Background loop — every 10s:
    When 2+ market orders from a signal are closed by TP,
    move remaining orders' SL to entry price (breakeven).
    """
    logger.info("Position monitor started (breakeven SL, polling every 10s).")
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        if not _groups:
            continue

        to_remove = []
        for magic, group in list(_groups.items()):
            try:
                open_tickets = _get_open_tickets(group.tickets)
                closed_count = group.initial_count - len(open_tickets)

                if not group.breakeven_triggered and closed_count >= 2:
                    logger.info(
                        f"[BREAKEVEN] {closed_count}/{group.initial_count} TPs hit "
                        f"(magic={magic}). Moving SL to entry {group.entry} "
                        f"on {len(open_tickets)} remaining order(s)."
                    )
                    move_sl_to_breakeven(open_tickets, group.entry)
                    group.breakeven_triggered = True

                if not open_tickets:
                    to_remove.append(magic)

            except Exception as exc:
                logger.error(f"Error in monitor loop for magic={magic}: {exc}", exc_info=True)

        for magic in to_remove:
            _groups.pop(magic, None)
