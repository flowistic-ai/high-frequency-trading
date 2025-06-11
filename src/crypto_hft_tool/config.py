import os
from dotenv import load_dotenv
from typing import Dict, List

# Base data folder
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
data_folder = os.path.join(PROJECT_ROOT, "data")

# Create data directory structure
os.makedirs(os.path.join(data_folder, "raw"), exist_ok=True)
os.makedirs(os.path.join(data_folder, "processed"), exist_ok=True)

# Load .env into os.environ
load_dotenv()

# Trading pairs
SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT'
]

# Data Provider Mode ('simulated' or 'ccxt')
DATA_PROVIDER_MODE = "simulated"

# API Configuration
API_HOST = "127.0.0.1"
API_PORT = 8000

# Target Exchange (for single exchange mode)
TARGET_EXCHANGE = "binance"

# Logging Level
LOG_LEVEL = "INFO"

ARBITRAGE_EXCHANGES = {
    "primary": "binance",
    "secondary": "kraken" # Ensure your CCXT or data provider setup supports this
}

# Minimum spread percentage for trading
MIN_SPREAD_PCT = 0.001  # 0.1%

# Enhanced Signal Settings
ENHANCED_SIGNAL_SETTINGS = {
    'volatility_window': 10,        # Reduced from 15 to be more responsive
    'correlation_window': 30,       # Reduced from 50 to be more responsive
    'momentum_window': 5,          # Reduced from 10 to be more responsive
    'signal_threshold': 0.4,       # Reduced from 0.8 to generate more signals
    'vol_impact': 0.05            # Reduced from 0.1 to be less sensitive to volatility
}

# Websocket endpoints
WS_ENDPOINTS = {
    'binance': 'wss://stream.binance.com:9443/ws',
    'kraken': 'wss://ws.kraken.com'
}

# Performance monitoring settings
MONITORING_SETTINGS = {
    'metrics_window': 1000,  # Number of data points to keep
    'update_interval': 5,    # seconds
    'alert_thresholds': {
        'latency': 100,      # ms
        'slippage': 0.001,   # 0.1%
        'fill_ratio': 0.95,
        'price_impact': 0.0005  # 0.05%
    }
}

# Exchange credentials (to be loaded from environment variables)
EXCHANGE_CREDENTIALS = {
    'binance': {
        'apiKey': os.getenv('BINANCE_API_KEY', ''),
        'secret': os.getenv('BINANCE_SECRET_KEY', '')
    },
    'kraken': {
        'apiKey': os.getenv('KRAKEN_API_KEY', ''),
        'secret': os.getenv('KRAKEN_SECRET_KEY', '')
    }
}

# ----------------------------------------
# Trading fees (in decimal form)
# Adjust these to match real exchange maker/taker rates
FEES = {
    "binance": {
        "maker": 0.0002,   # 0.02%
        "taker": 0.00001,   # Temporarily reduced from 0.04% for simulation
    },
    "kraken": {
        "maker": 0.00016,  # 0.016%
        "taker": 0.00001,   # Temporarily reduced from 0.026% for simulation
    },
}
# ----------------------------------------
# Risk management parameters

# Maximum notional exposure per symbol (in base-asset units)
# MAX_NOTIONAL_PER_TRADE = {
#     "BTC/USDT": 0.002,
#     "ETH/USDT": 0.03,
# }

# Maximum active notional exposure across all trades
# MAX_TOTAL_NOTIONAL = 0.01  # e.g., 0.01 BTC equivalent

# Stop-loss per trade (in spread units)
# e.g., if we trade expecting spread to decrease, exit if it increases by this amount from entry
# STOP_LOSS_SPREAD_AMOUNT = 5.0 # Example: Exit if spread moves 5.0 USDT against the trade

# Maximum cumulative drawdown before halting new trades
# MAX_DRAWDOWN = -0.005 # Example, adjust as needed

# Trade Execution Settings
TRADE_SETTINGS = {
    'execution': {
        'min_trade_interval': 1,      # Keep at 1 second
        'max_concurrent_trades': 5,    # Keep at 5
        'order_timeout': 5,           # Keep at 5 seconds
    },
    'position_sizing': {
        'min_size': {
            'BTC/USDT': 0.0001,       # Keep minimum sizes
            'ETH/USDT': 0.001,
            'default': 0.001
        },
        'max_size': {
            'BTC/USDT': 0.005,        # Reduced from 0.01 for smaller positions
            'ETH/USDT': 0.05,         # Reduced from 0.1 for smaller positions
            'default': 0.05
        },
        'size_increment': {
            'BTC/USDT': 0.0001,
            'ETH/USDT': 0.001,
            'default': 0.001
        }
    },
    'thresholds': {
        'min_spread_ratio': 0.00005,  # Reduced from 0.0001
        'max_spread_ratio': 0.005,    # Reduced from 0.01
        'min_profit_after_fees': {
            'BTC/USDT': 0.000005,     # Reduced from 0.00001
            'ETH/USDT': 0.00001,      # Reduced from 0.00002
            'default': 0.000005
        }
    }
}

# Z-score Settings
ZSCORE_SETTINGS = {
    'windows': [15, 60, 180, 360],  # Reduced windows for faster response
    'momentum_window': 10,          # Reduced from 20
    'correlation_window': 30,       # Reduced from 50
    'vol_window': 15,              # Reduced from 30
    'vol_impact': 0.15,            # Reduced from 0.3
    'thresholds': {
        'entry': {
            'min': 0.8,            # Reduced from 1.5
            'max': 1.5,            # Reduced from 3.0
            'ultra_short': 0.8,    # Reduced from 1.5
            'short': 1.0,          # Reduced from 2.0
            'medium': 1.2,         # Reduced from 2.5
            'long': 1.5            # Reduced from 3.0
        },
        'exit': {
            'ultra_short': 0.3,    # Reduced from 0.5
            'short': 0.4,          # Reduced from 0.8
            'medium': 0.5,         # Reduced from 1.0
            'long': 0.6            # Reduced from 1.2
        }
    },
    'vol_adjustment': True
}

# Risk Management Settings
RISK_SETTINGS = {
    'max_position_value': {
        'BTC/USDT': 50000,   # Maximum position value in USDT
        'ETH/USDT': 25000,
        'default': 10000
    },
    'max_drawdown': {
        'hourly': 0.02,      # 2% maximum hourly drawdown
        'daily': 0.05,       # 5% maximum daily drawdown
        'total': 0.10        # 10% maximum total drawdown
    },
    'stop_loss': {
        'spread_multiplier': 2.0,  # Stop loss at 2x entry spread
        'max_loss_per_trade': 0.01 # 1% maximum loss per trade
    }
}
