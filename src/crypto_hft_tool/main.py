from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware # Import CORS Middleware
from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Union, Any
import pandas as pd # For pd.Timestamp
import logging # Import logging
import time
from datetime import datetime, timezone
import asyncio
print(">>> RUNNING main.py FROM:", __file__)

# Update imports to use new class names
from .data_provider import BaseDataProvider, SimulatedSingleExchangeDataProvider
from .signals import RollingZScore
from .simulation import TradeSimulator
# from .risk_manager import RiskManager # Removed
from .enhanced_signals import EnhancedSignalProcessor, SignalMetrics
from .config import (
    SYMBOLS, TRADE_SETTINGS, ZSCORE_SETTINGS, # RISK_SETTINGS, # Removed
    DATA_PROVIDER_MODE, LOG_LEVEL, TARGET_EXCHANGE, ENHANCED_SIGNAL_SETTINGS,
    API_PORT, API_HOST, FEES, MIN_SPREAD_PCT, # STOP_LOSS_SPREAD_AMOUNT, # Removed
    ARBITRAGE_EXCHANGES
)

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Crypto HFT Tool API",
    description="API for the Crypto High-Frequency Trading Tool simulation and data.",
    version="0.1.0"
)

# --- CORS Middleware Configuration ---
# List of origins that are allowed to make requests to this backend.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# --- Global State Management (Simplified for initial setup) ---
# In a production app, consider more robust state management or dependency injection.

# Initialize DataProvider based on mode
data_provider: BaseDataProvider = SimulatedSingleExchangeDataProvider(symbols=SYMBOLS)
logger.info("Using SimulatedSingleExchangeDataProvider.")

# Store ZScore trackers per symbol
# We need a default window size for RollingZScore if not dynamically configured per symbol via API
DEFAULT_ZSCORE_WINDOW = 30  # Reduced from 100 to use less memory
# Update to use all symbols instead of limiting to 3
ACTIVE_SYMBOLS = SYMBOLS  # Track all symbols
zscore_trackers: Dict[str, RollingZScore] = {}
simulator = TradeSimulator()
# risk_manager = RiskManager() # Removed

# Initialize enhanced signal processors
enhanced_signal_processors = {}
for symbol in ACTIVE_SYMBOLS:
    zscore_trackers[symbol] = RollingZScore(windows=[DEFAULT_ZSCORE_WINDOW])
    enhanced_signal_processors[symbol] = EnhancedSignalProcessor(
        symbol=symbol,
        volatility_window=ENHANCED_SIGNAL_SETTINGS['volatility_window'],
        correlation_window=ENHANCED_SIGNAL_SETTINGS['correlation_window'],
        momentum_window=ENHANCED_SIGNAL_SETTINGS['momentum_window'],
        signal_threshold=ENHANCED_SIGNAL_SETTINGS['signal_threshold'],
        vol_impact=ENHANCED_SIGNAL_SETTINGS['vol_impact']
    )

# --- Constants/Configurable Params (used in logic) ---
# Ideally, load from config.py or environment variables
Z_SCORE_THRESHOLD = 1.2
TRADE_AMOUNT = 0.001
EXIT_Z_THRESHOLD = 0.3
TRADE_COOLDOWN_SEC = 30  # Minimum seconds between trades per symbol
last_trade_time = {sym: 0 for sym in ACTIVE_SYMBOLS}  # Only initialize for active symbols

# --- Pydantic Models for API Request/Response ---
class BookLevel(BaseModel):
    bid: float
    ask: float

class PositionMetrics(BaseModel):
    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    duration: float
    risk_score: float

class PortfolioMetrics(BaseModel):
    volatility: Dict[str, float]
    correlations: Dict[str, Dict[str, float]]
    var: Dict[str, float]
    portfolio_var: float
    sharpe_ratios: Dict[str, float]
    max_drawdowns: Dict[str, float]

class MarketDataResponse(BaseModel):
    timestamp: str
    symbol: str
    bid_price: float
    ask_price: float
    mid_price: float
    total_volume: float
    signal: str = "HOLD"
    trade_executed: bool = False
    reason: str = "Initial state"
    raw_zscore: Optional[float] = None
    volume_weighted_zscore: Optional[float] = None
    momentum_score: Optional[float] = None
    correlation_filter: Optional[float] = None
    volatility: Optional[float] = None
    adaptive_threshold: Optional[float] = None
    signal_strength: Optional[float] = None

class MarketDataAllResponse(BaseModel):
    data: Dict[str, MarketDataResponse]
    portfolio_pnl: float = 0.0

class SimulationStatusResponse(BaseModel):
    total_pnl: float
    total_trades: int
    win_rate: float
    avg_pnl_per_trade: float
    total_fees_paid: float
    # Strategy Parameters
    z_score_threshold: float
    trade_amount: float
    exit_z_threshold: float

class RecentTradesResponse(BaseModel):
    trades: List[Dict[str, Any]]

class LeaderboardEntry(BaseModel):
    symbol: str
    total_pnl: float
    trade_count: int

class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]

class TradeDetail(BaseModel):
    timestamp: str
    symbol: str
    buy_exchange: str
    buy_price: float
    sell_exchange: str
    sell_price: float
    amount: float
    pnl: float

# --- Background Trading Loop ---
async def trading_loop():
    logger.info("Background trading loop started.")
    while True:
        try:
            for symbol in ACTIVE_SYMBOLS:
                primary_ex = ARBITRAGE_EXCHANGES["primary"]
                secondary_ex = ARBITRAGE_EXCHANGES["secondary"]
                data_primary = await data_provider.get_market_data_rest(symbol, primary_ex)
                data_secondary = await data_provider.get_market_data_rest(symbol, secondary_ex)
                if not data_primary or not data_secondary:
                    continue
                bid_primary = float(data_primary['bid'])
                ask_primary = float(data_primary['ask'])
                bid_secondary = float(data_secondary['bid'])
                ask_secondary = float(data_secondary['ask'])
                vol_primary = float(data_primary.get('baseVolume', 0) or data_primary.get('volume', 0))
                vol_secondary = float(data_secondary.get('baseVolume', 0) or data_secondary.get('volume', 0))
                avg_volume = (vol_primary + vol_secondary) / 2
                api_timestamp_str = data_primary['timestamp']
                if 'Z' in api_timestamp_str:
                    timestamp_dt = datetime.fromisoformat(api_timestamp_str.replace('Z', '+00:00'))
                else:
                    try:
                        timestamp_dt = datetime.fromisoformat(api_timestamp_str)
                    except ValueError:
                        try:
                            timestamp_dt = datetime.fromtimestamp(float(api_timestamp_str)/1000)
                        except ValueError:
                            timestamp_dt = datetime.utcnow()
                # Calculate spread for signal processing
                current_market_spread_for_signal = bid_primary - ask_secondary
                signal_metrics = enhanced_signal_processors[symbol].update(
                    spread=current_market_spread_for_signal,
                    volume=avg_volume,
                    timestamp=timestamp_dt
                )
                best_metrics = None
                if signal_metrics:
                    best_metrics = max(signal_metrics.values(), key=lambda x: x.signal_strength)
                # Check cooldown
                now = time.time()
                if now - last_trade_time[symbol] < TRADE_COOLDOWN_SEC:
                    continue
                # Determine trading signal and simulate trade
                if best_metrics and best_metrics.signal_strength >= best_metrics.threshold:
                    if best_metrics.zscore > 0:
                        profit = float(bid_primary) - float(ask_secondary)
                        min_profit = TRADE_SETTINGS['thresholds']['min_profit_after_fees'].get(
                            symbol, TRADE_SETTINGS['thresholds']['min_profit_after_fees']['default']
                        )
                        if profit >= min_profit:
                            simulator.simulate_arbitrage_trade(
                                symbol=symbol,
                                amount=TRADE_AMOUNT,
                                buy_exchange=secondary_ex,
                                buy_price=ask_secondary,
                                sell_exchange=primary_ex,
                                sell_price=bid_primary,
                                buy_fee_rate=FEES[secondary_ex]["taker"],
                                sell_fee_rate=FEES[primary_ex]["taker"]
                            )
                            last_trade_time[symbol] = now
                    else:
                        profit = float(bid_secondary) - float(ask_primary)
                        min_profit = TRADE_SETTINGS['thresholds']['min_profit_after_fees'].get(
                            symbol, TRADE_SETTINGS['thresholds']['min_profit_after_fees']['default']
                        )
                        if profit >= min_profit:
                            simulator.simulate_arbitrage_trade(
                                symbol=symbol,
                                amount=TRADE_AMOUNT,
                                buy_exchange=primary_ex,
                                buy_price=ask_primary,
                                sell_exchange=secondary_ex,
                                sell_price=bid_secondary,
                                buy_fee_rate=FEES[primary_ex]["taker"],
                                sell_fee_rate=FEES[secondary_ex]["taker"]
                            )
                            last_trade_time[symbol] = now
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
        await asyncio.sleep(1)  # Check every second

# --- API Endpoints ---
@app.on_event("startup")
async def startup_event():
    """Initialize application state on startup."""
    logger.info("FastAPI application startup complete.")
    
    # Initialize ZScore trackers for all symbols
    for symbol in ACTIVE_SYMBOLS:
        zscore_trackers[symbol] = RollingZScore(windows=[DEFAULT_ZSCORE_WINDOW])
        enhanced_signal_processors[symbol] = EnhancedSignalProcessor(
            symbol=symbol,
            volatility_window=ENHANCED_SIGNAL_SETTINGS['volatility_window'],
            correlation_window=ENHANCED_SIGNAL_SETTINGS['correlation_window'],
            momentum_window=ENHANCED_SIGNAL_SETTINGS['momentum_window'],
            signal_threshold=ENHANCED_SIGNAL_SETTINGS['signal_threshold'],
            vol_impact=ENHANCED_SIGNAL_SETTINGS['vol_impact']
        )
    
    # Initialize simulator parameters
    simulator.update_settings(
        z_score_threshold=Z_SCORE_THRESHOLD,
        trade_amount=TRADE_AMOUNT,
        exit_z_threshold=EXIT_Z_THRESHOLD
    )
    
    # Start data generation
    await data_provider.start_data_generation()
    
    # Initialize historical data for each symbol
    for symbol in ACTIVE_SYMBOLS:
        for exchange in [ARBITRAGE_EXCHANGES["primary"], ARBITRAGE_EXCHANGES["secondary"]]:
            historical_data = await data_provider.get_historical_data(
                symbol=symbol,
                exchange_name=exchange,
                timeframe="1m",
                limit=100  # Get initial history
            )
            if historical_data is not None:
                # Process historical data through signal processors
                for _, row in historical_data.iterrows():
                    spread = row['bid'] - row['ask']
                    volume = row['volume']
                    timestamp = row.name  # Index is timestamp
                    enhanced_signal_processors[symbol].update(spread, volume, timestamp)
    
    # Start background trading loop
    asyncio.create_task(trading_loop())
    logger.info("All components initialized successfully.")

@app.get("/")
async def read_root():
    return {"message": "Welcome to Crypto HFT Tool API"}

@app.get("/api/v1/market_data/all", response_model=MarketDataAllResponse)
async def get_all_market_data():
    try:
        data = {}
        for symbol in SYMBOLS:
            market_data = await data_provider.get_market_data_rest(symbol, TARGET_EXCHANGE)
            if market_data:
                data[symbol] = MarketDataResponse(
                    timestamp=market_data['timestamp'],
                    symbol=market_data['symbol'],
                    bid_price=market_data['bid'],
                    ask_price=market_data['ask'],
                    mid_price=market_data['mid_price'],
                    total_volume=market_data['baseVolume']
                )
        return MarketDataAllResponse(data=data)
    except Exception as e:
        logger.error(f"Error getting market data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/market_data/{symbol:path}", response_model=MarketDataResponse)
async def get_market_data(
    symbol: str = Path(..., description="The symbol to get market data for, e.g., BTC/USDT")
):
    try:
        market_data = await data_provider.get_market_data_rest(symbol, TARGET_EXCHANGE)
        if not market_data:
            raise HTTPException(status_code=404, detail=f"Market data not found for {symbol}")
        
        return MarketDataResponse(
            timestamp=market_data['timestamp'],
            symbol=market_data['symbol'],
            bid_price=market_data['bid'],
            ask_price=market_data['ask'],
            mid_price=market_data['mid_price'],
            total_volume=market_data['baseVolume']
        )
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/simulation/status", response_model=SimulationStatusResponse)
async def get_simulation_status():
    """
    Get the current status of the trade simulation (e.g., PnL, total trades).
    """
    total_trades = len(simulator.trades)
    winning_trades = sum(1 for trade in simulator.trades if trade.get('pnl', 0) > 0)
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
    avg_pnl_per_trade = simulator.total_pnl / total_trades if total_trades > 0 else 0.0

    return SimulationStatusResponse(
        total_pnl=simulator.total_pnl,
        total_trades=total_trades,
        win_rate=win_rate,
        avg_pnl_per_trade=avg_pnl_per_trade,
        total_fees_paid=simulator.total_fees_paid,
        # Strategy Parameters from main.py globals
        z_score_threshold=Z_SCORE_THRESHOLD,
        trade_amount=TRADE_AMOUNT, # This is the global TRADE_AMOUNT
        exit_z_threshold=EXIT_Z_THRESHOLD
    )

@app.get("/api/v1/simulation/trades", response_model=RecentTradesResponse)
async def get_recent_trades(limit: int = 10):
    """
    Get a list of the most recent simulated trades.
    """
    recent_trades = []
    for trade_dict in reversed(simulator.trades[-limit:]):
        trade_timestamp = trade_dict.get('timestamp')
        timestamp_str = "Invalid Timestamp" # Default / error value

        try:
            if isinstance(trade_timestamp, pd.Timestamp):
                # Ensure timezone is UTC before formatting
                if trade_timestamp.tzinfo is None:
                    ts_obj = trade_timestamp.tz_localize('UTC')
                else:
                    ts_obj = trade_timestamp.tz_convert('UTC')
                # Format to ISO string with Z for UTC, milliseconds precision
                timestamp_str = ts_obj.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            elif isinstance(trade_timestamp, (int, float)):
                # Convert from Unix timestamp, assuming UTC
                ts_obj = pd.Timestamp.fromtimestamp(trade_timestamp, tz='UTC')
                timestamp_str = ts_obj.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            elif isinstance(trade_timestamp, str):
                 # Attempt to parse string, assuming UTC if no tzinfo
                ts_obj = pd.Timestamp(trade_timestamp)
                if ts_obj.tzinfo is None:
                    ts_obj = ts_obj.tz_localize('UTC')
                else:
                    ts_obj = ts_obj.tz_convert('UTC')
                timestamp_str = ts_obj.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

        except Exception as e:
            logger.error(f"Error formatting timestamp '{trade_timestamp}': {e}")
            # timestamp_str remains "Invalid Timestamp"

        recent_trades.append({
            "timestamp": timestamp_str,
            "symbol": trade_dict.get('symbol', 'N/A'),
            "buy_exchange": trade_dict.get('buy_exchange', 'N/A'),
            "buy_price": trade_dict.get('buy_price', 0.0),
            "sell_exchange": trade_dict.get('sell_exchange', 'N/A'),
            "sell_price": trade_dict.get('sell_price', 0.0),
            "amount": trade_dict.get('amount', 0.0),
            "pnl": trade_dict.get('pnl', 0.0)
        })
    return RecentTradesResponse(trades=recent_trades)

@app.get("/api/v1/simulation/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard():
    """
    Return leaderboard of all symbols by total PnL and trade count.
    """
    # Aggregate trades by symbol
    symbol_stats = {sym: {"total_pnl": 0.0, "trade_count": 0} for sym in SYMBOLS}
    for trade in simulator.trades:
        sym = trade.get("symbol", None)
        if sym in symbol_stats:
            symbol_stats[sym]["total_pnl"] += trade.get("pnl", 0.0)
            symbol_stats[sym]["trade_count"] += 1
    leaderboard = [
        LeaderboardEntry(symbol=sym, total_pnl=stats["total_pnl"], trade_count=stats["trade_count"])
        for sym, stats in symbol_stats.items()
    ]
    leaderboard.sort(key=lambda x: x.total_pnl, reverse=True)
    return LeaderboardResponse(leaderboard=leaderboard)

# To run the server (save this as main.py in src/crypto_hft_tool/):
# Ensure your terminal is in the root of your project (crypto_hft_tool folder, not src)
# Then run: uvicorn src.crypto_hft_tool.main:app --reload --port 8000