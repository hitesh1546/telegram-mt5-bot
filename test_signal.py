"""
Test harness for signal parsing and MT5 order placement, without waiting for a live signal.

Usage:
    python test_signal.py --last                    # fetch the most recent channel message, preview only
    python test_signal.py --text "GOLD BUY 4377..."  # test with manual raw text, preview only
    python test_signal.py --last --execute           # actually place the order (uses .env DRY_RUN, confirms if live)

Uses a separate Telegram session (test_session.session, copied from tg_session.session on
first run) so this can run alongside the live bot without touching its session file.
"""
import argparse
import asyncio
import os
import shutil

from telethon import TelegramClient
from telethon.tl.types import PeerChannel

import config
from signal_parser import parse_signal
from mt5_trader import initialize_mt5, place_trade
from position_monitor import track_signal

TEST_SESSION = "test_session"


def _ensure_test_session() -> None:
    if not os.path.exists(f"{TEST_SESSION}.session") and os.path.exists("tg_session.session"):
        shutil.copy("tg_session.session", f"{TEST_SESSION}.session")


async def fetch_last_message() -> str:
    _ensure_test_session()
    client = TelegramClient(TEST_SESSION, config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)
    await client.connect()
    try:
        channel_ref = PeerChannel(config.TELEGRAM_CHANNEL_ID) if config.TELEGRAM_CHANNEL_ID else config.TELEGRAM_CHANNEL
        channel = await client.get_entity(channel_ref)
        messages = await client.get_messages(channel, limit=1)
        if not messages:
            raise RuntimeError("No messages found in channel.")
        return messages[0].text or ""
    finally:
        await client.disconnect()


def _apply_more_entry_averaging(signal: dict) -> dict:
    """Mirrors telegram_listener.py's handling of a 'MORE' second-entry line."""
    entry2 = signal.get("entry2")
    if entry2 is None:
        return signal
    entry1 = signal.get("entry")
    avg_entry = (entry1 + entry2) / 2 if entry1 is not None else entry2
    tp_list = signal.get("tp") or []
    return {**signal, "entry": avg_entry, "tp": tp_list[:2] or None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test signal parsing and MT5 order placement.")
    parser.add_argument("--last", action="store_true", help="Fetch the most recent message from the configured channel.")
    parser.add_argument("--text", type=str, help="Test with manual raw signal text instead of fetching from Telegram.")
    parser.add_argument("--execute", action="store_true", help="Actually place the order (uses real DRY_RUN from .env). Without this flag, always previews only.")
    args = parser.parse_args()

    if not args.last and not args.text:
        parser.error("Provide --last or --text")

    raw_text = asyncio.run(fetch_last_message()) if args.last else args.text
    print(f"--- Raw message ---\n{raw_text}\n")

    signal = parse_signal(raw_text)
    print(f"--- Parsed signal ---\n{signal}\n")

    if not signal.get("is_signal"):
        print("Not a trade signal — nothing to place.")
        return

    action = (signal.get("action") or "").upper()
    if action not in ("BUY", "SELL"):
        print(f"Action '{action}' not handled by this test script.")
        return

    signal = _apply_more_entry_averaging(signal)
    if signal.get("entry2") is not None:
        print(f"--- After MORE-entry averaging ---\n{signal}\n")

    if not args.execute:
        print("[PREVIEW ONLY] Pass --execute to actually place this order (uses your .env DRY_RUN setting).")
        return

    if not config.DRY_RUN:
        print("\n*** WARNING: DRY_RUN=false in .env — this WILL place a REAL order on a REAL account. ***")
        if input("Type 'yes' to continue: ").strip().lower() != "yes":
            print("Aborted.")
            return

    if not initialize_mt5():
        print("MT5 initialization failed.")
        return

    success, magic, tickets, entry = place_trade(signal)
    print(f"\n--- Result ---\nsuccess={success}, magic={magic}, tickets={tickets}, entry={entry}")
    if success and tickets:
        track_signal(magic, entry, tickets)


if __name__ == "__main__":
    main()
