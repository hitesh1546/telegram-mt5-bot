import asyncio
import sys

import config
from logger import get_logger
from mt5_trader import initialize_mt5, get_account_info
from telegram_listener import start_listener
from position_monitor import monitor_loop

logger = get_logger()


def print_startup_summary(account_info) -> None:
    trade_mode = "DRY RUN (no trades will be executed)" if config.DRY_RUN else "LIVE TRADING"
    channel_tag = (
        "[TEST]" if config.TELEGRAM_CHANNEL == config.CHANNEL_TEST
        else "[LIVE]" if config.TELEGRAM_CHANNEL == config.CHANNEL_LIVE
        else ""
    )
    sep = "=" * 55
    lines = [
        "",
        sep,
        "  Telegram -> MT5 Signal Bot",
        sep,
        f"  Trade mode : {trade_mode}",
        f"  Strategy   : Pending limit at TP1, exit at TP2 (1:1 RR)",
        f"  Account    : {account_info.login}",
        f"  Server     : {account_info.server}",
        f"  Balance    : {account_info.balance:.2f} {account_info.currency}",
        f"  Risk       : {config.RISK_PERCENT}% per trade",
        f"  Channel    : {channel_tag} {config.TELEGRAM_CHANNEL}",
        sep,
    ]
    logger.info("\n".join(lines))


async def main() -> None:
    logger.info("Starting Telegram-MT5 signal bot...")

    if not initialize_mt5(retries=3):
        logger.error("Cannot connect to MT5. Exiting.")
        sys.exit(1)

    account_info = get_account_info()
    if not account_info:
        logger.error("Cannot fetch MT5 account info. Exiting.")
        sys.exit(1)

    print_startup_summary(account_info)

    try:
        # Run Telegram listener and breakeven monitor concurrently
        await asyncio.gather(
            start_listener(),
            monitor_loop(),
        )
    except KeyboardInterrupt:
        logger.info("Shutdown requested — exiting gracefully.")
    except Exception as exc:
        logger.error(f"Fatal error: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
