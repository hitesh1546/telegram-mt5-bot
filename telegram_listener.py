import asyncio

from telethon import TelegramClient, events
from telethon.tl.types import Message

import config
from logger import get_logger
from signal_parser import parse_signal
from mt5_trader import place_trade, close_trade
from position_monitor import track_signal

logger = get_logger()

SESSION_NAME = "tg_session"


async def handle_message(event: events.NewMessage.Event) -> None:
    message: Message = event.message
    raw_text = (message.text or "").strip()

    if not raw_text:
        logger.debug("Empty message received — skipping.")
        return

    logger.info(f"New message from channel: {raw_text[:120]!r}")

    signal = parse_signal(raw_text)
    if signal is None:
        logger.warning("Signal parsing returned None — skipping trade.")
        return

    if not signal.get("is_signal"):
        logger.info("Message is not a trade signal — ignoring.")
        return

    action = (signal.get("action") or "").upper()

    if action == "CLOSE":
        symbol = signal.get("symbol")
        if symbol:
            logger.info(f"CLOSE signal received for {symbol}")
            close_trade(symbol)
        else:
            logger.warning("CLOSE signal has no symbol — skipping.")

    elif action in ("BUY", "SELL"):
        # 5 market orders (one per TP) + breakeven monitor
        success, magic, tickets, entry = place_trade(signal)
        if success and tickets:
            track_signal(magic, entry, tickets)

    else:
        logger.warning(f"Unknown action '{action}' — skipping.")


async def start_listener() -> None:
    client = TelegramClient(SESSION_NAME, config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)

    await client.start()
    logger.info("Telegram client started.")

    try:
        channel = await client.get_entity(config.TELEGRAM_CHANNEL)
        title = getattr(channel, "title", config.TELEGRAM_CHANNEL)
        mode_tag = (
            "[TEST]" if config.TELEGRAM_CHANNEL == config.CHANNEL_TEST
            else "[LIVE]" if config.TELEGRAM_CHANNEL == config.CHANNEL_LIVE
            else ""
        )
        logger.info(f"Monitoring channel {mode_tag}: {title} ({config.TELEGRAM_CHANNEL})")
    except Exception as exc:
        logger.error(f"Failed to resolve channel '{config.TELEGRAM_CHANNEL}': {exc}")
        raise

    @client.on(events.NewMessage(chats=channel))
    async def _handler(event: events.NewMessage.Event) -> None:
        try:
            await handle_message(event)
        except Exception as exc:
            logger.error(f"Unhandled error in message handler: {exc}", exc_info=True)

    logger.info("Listening for new messages... (Ctrl+C to stop)")
    await client.run_until_disconnected()
