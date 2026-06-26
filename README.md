# Telegram → MT5 Signal Bot

Automatically monitors a Telegram channel for forex/gold trading signals and executes trades on MetaTrader 5.

## Features

- Monitors Telegram channel in real-time using Telethon
- Parses signals using regex (no AI needed) — handles bold Unicode text from signal channels
- Places **one market order per TP level** (e.g. 5 TPs = 5 orders)
- **Breakeven SL monitor** — after 2 TPs hit, remaining orders' SL moves to entry automatically
- Risk-based lot sizing (% of account balance)
- **DRY_RUN mode** — logs everything without sending real orders (safe for testing)
- Logs to both console and `trades.log` file

## Signal Format Supported

```
✅𝐗𝐀𝐔𝐔𝐒𝐃 BUY  3992✅

✅𝐓𝐏. 3996
✅𝐓𝐏. 3998
✅𝐓𝐏. 4000
✅𝐓𝐏. 4002
✅𝐓𝐏. 4004

✅𝐒𝐥. 3985
```

Ignores result/update messages like "TP 4 HIT +120 PIPS PROFIT DONE".

## Requirements

- **Windows only** (MT5 Python library is Windows-only)
- MetaTrader 5 terminal installed and logged in
- Python 3.10+
- Telegram account (member of the signal channel)

## Installation

```cmd
git clone https://github.com/hitesh1546/telegram-mt5-bot.git
cd telegram-mt5-bot
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```ini
TELEGRAM_API_ID=          # from my.telegram.org
TELEGRAM_API_HASH=        # from my.telegram.org
TELEGRAM_CHANNEL=         # e.g. https://t.me/yourchannel

MT5_ACCOUNT=              # MT5 account number
MT5_PASSWORD=             # MT5 password
MT5_SERVER=               # e.g. Exness-MT5Trial8

RISK_PERCENT=1            # % of balance risked per trade
DEFAULT_LOT=0.1           # fallback lot size
DRY_RUN=true              # set false for live trading
```

### Get Telegram API credentials
1. Go to [my.telegram.org](https://my.telegram.org)
2. Click **API development tools**
3. Create an app — copy `api_id` and `api_hash`

## Usage

```cmd
python main.py
```

First run will ask for your Telegram phone number + OTP. After that, session is saved automatically.

## How It Works

```
Telegram signal received
        ↓
Regex parser extracts: symbol, action, entry, SL, TPs
        ↓
N market orders placed (one per TP), shared SL, unique magic number
        ↓
Background monitor polls every 10 seconds
        ↓
2+ TPs hit → remaining orders' SL moved to entry (breakeven, no loss)
        ↓
All orders closed → signal group removed from tracker
```

## Project Structure

```
telegram_mt5/
├── main.py               # Entry point, startup summary, asyncio orchestration
├── config.py             # Environment variable loading & validation
├── telegram_listener.py  # Telethon channel monitor & signal routing
├── signal_parser.py      # Regex-based signal parser
├── mt5_trader.py         # MT5 order placement, breakeven SL, close trade
├── risk_manager.py       # Lot size calculation based on risk %
├── position_monitor.py   # Background breakeven SL monitor loop
├── logger.py             # Dual console + file logger
├── requirements.txt      # Dependencies
└── .env                  # Credentials (not committed)
```

## Risk Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RISK_PERCENT` | 1% | % of balance risked per signal |
| Min lot | 0.01 | MT5 minimum |
| Max lot | 1.0 | Hard cap |

Lot size = `(Balance × Risk%) ÷ (SL pips × pip value)`

- XAUUSD: pip = $0.01, pip value = $1/lot
- Forex: pip = $0.0001, pip value = $10/lot

## Running on Startup (Windows)

Use **Task Scheduler** to auto-start on boot:
- Program: `C:\path\to\python.exe`
- Arguments: `main.py`
- Start in: `C:\path\to\telegram-mt5-bot`

## Notes

- MT5 terminal must be **open and logged in** before running the bot
- The bot does **not** close trades — only manages SL after TP hits
- `tg_session.session` is created after first login — keep it safe, do not share
- `.env` is excluded from git — never commit your credentials

## Dependencies

```
telethon
MetaTrader5
python-dotenv
```
