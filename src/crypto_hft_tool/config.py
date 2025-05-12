import os
from dotenv import load_dotenv

# Base data folder
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
data_folder = os.path.join(PROJECT_ROOT, "data")

# Create data directory structure
os.makedirs(os.path.join(data_folder, "raw"), exist_ok=True)
os.makedirs(os.path.join(data_folder, "processed"), exist_ok=True)

# Load .env into os.environ
load_dotenv()

# API credentials pulled from environment variables
EXCHANGE_CREDENTIALS = {
    "binance": {
        "apiKey": os.getenv("BINANCE_API_KEY", ""),
        "secret": os.getenv("BINANCE_SECRET", ""),
    },
    "kraken": {
        "apiKey": os.getenv("KRAKEN_API_KEY", ""),
        "secret": os.getenv("KRAKEN_SECRET", ""),
    },
}

# WebSocket endpoints (if you want to override defaults)
WS_ENDPOINTS = {
    "binance": "wss://stream.binance.com:9443/ws",
    "kraken": "wss://ws.kraken.com",
}

# Which symbol pair(s) to subscribe to
SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "LTC/USDT", "XRP/USDT", "BCH/USDT", "ADA/USDT", "SOL/USDT", "DOGE/USDT", "DOT/USDT", "LINK/USDT"
]

# ----------------------------------------
# Trading fees (in decimal form)
# Adjust these to match real exchange maker/taker rates
FEES = {
    "binance": {
        "maker": 0.0002,   # 0.02%
        "taker": 0.0004,   # 0.04%
    },
    "kraken": {
        "maker": 0.00016,  # 0.016%
        "taker": 0.00026,  # 0.026%
    },
}
# ----------------------------------------
# Risk management parameters

# Maximum notional exposure per symbol (in base-asset units)
MAX_NOTIONAL_PER_TRADE = {
    "BTC/USDT": 0.002,
    "ETH/USDT": 0.03,
    "LTC/USDT": 0.5,
    "XRP/USDT": 100,
    "BCH/USDT": 0.1,
    "ADA/USDT": 100,
    "SOL/USDT": 0.5,
    "DOGE/USDT": 500,
    "DOT/USDT": 2,
    "LINK/USDT": 2
}

# Maximum active notional exposure across all trades
MAX_TOTAL_NOTIONAL = 0.01  # e.g., 0.01 BTC equivalent

# Stop-loss per trade (in spread units)
# e.g., if we trade expecting spread to decrease, exit if it increases by this amount from entry
STOP_LOSS_SPREAD_AMOUNT = 5.0 # Example: Exit if spread moves 5.0 USDT against the trade

# Maximum cumulative drawdown before halting new trades
MAX_DRAWDOWN = -0.005 # Example, adjust as needed
