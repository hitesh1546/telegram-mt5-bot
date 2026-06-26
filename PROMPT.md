# AI Prompt — Build Telegram to MT5 Signal Bot

Use this prompt with Claude Code (or any AI coding assistant) to recreate this project from scratch.

---

## Prompt

Build a Telegram-to-MT5 trade execution system in Python.

### Overview
Monitor a Telegram channel for forex/gold trading signals and automatically execute trades on MetaTrader 5.

### Stack
- Python 3.10+
- Telethon (Telegram user API)
- MetaTrader5 Python library
- python-dotenv for config
- No AI/LLM needed for parsing — use regex

### Project Structure
```
telegram_mt5/
├── main.py               # Entry point
├── config.py             # Load env variables
├── telegram_listener.py  # Telethon channel monitor
├── signal_parser.py      # Regex signal parser
├── mt5_trader.py         # MT5 trade execution
├── risk_manager.py       # Lot size & risk calculation
├── position_monitor.py   # Breakeven SL background monitor
├── logger.py             # File + console logging
├── .env                  # Credentials (not committed)
└── requirements.txt
```

### .env variables
```ini
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_CHANNEL=         # username or invite link

MT5_ACCOUNT=
MT5_PASSWORD=
MT5_SERVER=               # e.g. Exness-MT5Trial8

RISK_PERCENT=1            # % of balance risked per trade
DEFAULT_LOT=0.1           # fallback lot size
DRY_RUN=false             # true = log only, no real orders
```

### signal_parser.py
Use regex (no AI) to parse raw signal text. The channel uses bold Unicode characters — use `unicodedata.normalize("NFKC", text)` to convert to plain ASCII before matching.

Signal format:
```
✅𝐗𝐀𝐔𝐔𝐒𝐃 BUY  3992✅
✅𝐓𝐏. 3996
✅𝐓𝐏. 3998
✅𝐓𝐏. 4000
✅𝐓𝐏. 4002
✅𝐓𝐏. 4004
✅𝐒𝐥. 3985
```

Return a dict:
```python
{
  "symbol": "XAUUSD",
  "action": "BUY",        # BUY | SELL | CLOSE
  "entry": 3992.0,
  "sl": 3985.0,
  "tp": [3996.0, 3998.0, 4000.0, 4002.0, 4004.0],
  "is_signal": True
}
```

Ignore messages containing: `TP HIT`, `TARGET COMPLETE`, `PROFIT DONE`, `ALL TARGET`, `PIPS PROFIT`.
Set `is_signal: False` for those.

### mt5_trader.py
Functions:
- `initialize_mt5(retries=3)` — login using .env credentials, retry 3 times
- `get_price(symbol, action)` — ask for BUY, bid for SELL
- `place_trade(signal)` — place N market orders (one per TP), lot split evenly across orders, unique magic number per signal using `int(time.time()) % 99_999_999`. Return `(success, magic, tickets, entry_price)`
- `move_sl_to_breakeven(tickets, entry)` — use `TRADE_ACTION_SLTP` to move SL to entry price on open positions
- `close_trade(symbol)` — close all open positions for symbol
- `get_open_positions(symbol)` — return list of open trades

### position_monitor.py
Background asyncio loop polling every 10 seconds.

Track signal groups in memory:
```python
@dataclass
class SignalGroup:
    magic: int
    entry: float
    tickets: list
    initial_count: int
    breakeven_triggered: bool = False
```

Logic per poll:
- Check how many tickets are still open positions in MT5
- If `closed_count >= 2` and breakeven not triggered → call `move_sl_to_breakeven()` on remaining open tickets
- If all tickets closed → remove group from tracker

### risk_manager.py
```python
def calculate_lot(symbol, entry, sl, risk_percent, balance):
    risk_amount = balance * (risk_percent / 100)
    
    # XAUUSD: pip = 0.01, pip_value = $1/lot
    # Forex:  pip = 0.0001, pip_value = $10/lot (JPY: 0.01)
    
    sl_pips = abs(entry - sl) / pip_size
    lot = risk_amount / (sl_pips * pip_value_per_lot)
    return max(0.01, min(1.0, round(lot, 2)))
```

### telegram_listener.py
- Use Telethon to monitor channel from .env
- On each new message: call `parse_signal()`
- If `is_signal=True` and action is BUY/SELL: call `place_trade()`, then `track_signal()`
- If action is CLOSE: call `close_trade(symbol)`
- Log every message and every trade attempt

### main.py
- Initialize MT5 (retry x3), exit if fails
- Print startup summary: balance, server, channel, mode (DRY RUN / LIVE)
- Run Telegram listener + position monitor concurrently: `await asyncio.gather(start_listener(), monitor_loop())`
- Handle graceful Ctrl+C shutdown

### logger.py
- Log to both console (UTF-8 encoded, important for Windows) and `trades.log` file
- Format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
- Helper: `log_section(logger, section_name, content)` for named blocks like SIGNAL RECEIVED, PARSED RESULT, TRADE EXECUTED

### Error handling
- MT5 not connected → log error, skip trade, do not crash
- Signal parse fails → log and skip
- `order_send` fails → log retcode and comment
- `DRY_RUN=true` → log everything, send no orders to MT5

### requirements.txt
```
telethon
MetaTrader5
python-dotenv
```

### Important notes
- MT5 Python library only works on Windows
- MT5 terminal must be running and logged in before script starts
- Use asyncio properly — Telethon is async
- Use UTF-8 encoding for console logger on Windows to avoid UnicodeEncodeError
- Build startup banner using a list of strings joined with `\n` — avoid adjacent string literal + expression concatenation (causes repetition bug)
- Unique magic number per signal: `int(time.time()) % 99_999_999`
- Use `ORDER_FILLING_IOC` for market orders, `ORDER_FILLING_RETURN` for pending orders
