from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware # Import CORS Middleware
from pydantic import BaseModel
from typing import Dict, Optional, List
import pandas as pd # For pd.Timestamp
import logging # Import logging
import time
print(">>> RUNNING main.py FROM:", __file__)

# Assuming your existing modules are structured to be importable like this:
from .data_provider import DataProvider
from .signals import RollingZScore
from .simulation import TradeSimulator
from .risk_manager import RiskManager
from .config import SYMBOLS, data_folder, STOP_LOSS_SPREAD_AMOUNT, FEES # Add FEES if needed by simulator/risk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Crypto HFT Tool API",
    description="API for the Crypto High-Frequency Trading Tool simulation and data.",
    version="0.1.0"
)

# --- CORS Middleware Configuration ---
# List of origins that are allowed to make requests to this backend.
# Use ["*"] for development if needed, but be more specific for production.
origins = [
    "http://localhost:3000", # React development server
    "http://localhost",      # Sometimes needed depending on browser/setup
    # Add any other origins if you deploy your frontend elsewhere later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Allow cookies if needed later
    allow_methods=["GET"], # Allow only GET requests for now
    allow_headers=["*"], # Allow all headers
)

# --- Global State Management (Simplified for initial setup) ---
# In a production app, consider more robust state management or dependency injection.

# Initialize DataProvider for live data by default for the API
# For a real app, you might want to configure this (e.g., via env vars or a config endpoint)
data_provider = DataProvider(live=True)
if data_provider.error:
    logger.critical(f"CRITICAL: DataProvider failed to initialize in live mode: {data_provider.error}")
    # You might want to prevent the app from starting or enter a degraded state

# Store ZScore trackers per symbol
# We need a default window size for RollingZScore if not dynamically configured per symbol via API
DEFAULT_ZSCORE_WINDOW = 100 # Reduced for more responsive signals
zscore_trackers: Dict[str, RollingZScore] = {}
simulator = TradeSimulator()
risk_manager = RiskManager()

# --- Constants/Configurable Params (used in logic) ---
# Ideally, load from config.py or environment variables
Z_SCORE_THRESHOLD = 1.2
TRADE_AMOUNT = 0.001
EXIT_Z_THRESHOLD = 0.3
STOP_LOSS_AMOUNT = STOP_LOSS_SPREAD_AMOUNT # Get from config
MIN_SPREAD_PCT = 0.00001  # Lowered to 0.001% of price as minimum spread for arbitrage
TRADE_COOLDOWN_SEC = 30  # Minimum seconds between trades per symbol
last_trade_time = {sym: 0 for sym in SYMBOLS}

# --- Pydantic Models for API Request/Response ---
class BookLevel(BaseModel):
    bid: float
    ask: float

class MarketDataResponse(BaseModel):
    timestamp: str
    symbol: str
    binance: BookLevel
    kraken: BookLevel
    spread: float
    z_score: Optional[float] = None # Z-score might not be available if not enough data
    error: Optional[str] = None

class TradeDetail(BaseModel):
    timestamp: str # Assuming TradeSimulator records trades with timestamps
    symbol: str
    buy_exchange: str
    buy_price: float
    sell_exchange: str
    sell_price: float
    amount: float
    pnl: float
    # Add other fields from your simulator.trades if they exist e.g. fees

class SimulationStatusResponse(BaseModel):
    total_pnl: float
    total_trades: int
    # Strategy Parameters
    z_score_threshold: float
    trade_amount: float
    exit_z_threshold: float
    stop_loss_amount: float

class RecentTradesResponse(BaseModel):
    trades: List[TradeDetail]

# New model for Sentiment
class SentimentResponse(BaseModel):
    symbol: str
    sentiment_label: str = "neutral" # e.g., bullish, bearish, neutral
    sentiment_score: float = 0.0 # e.g., range from -1.0 (very bearish) to 1.0 (very bullish)
    source: str = "placeholder" # Indicates this is not from a live source yet
    timestamp: Optional[str] = None # Timestamp when sentiment was assessed

class MarketDataAllResponse(BaseModel):
    data: Dict[str, MarketDataResponse]

class LeaderboardEntry(BaseModel):
    symbol: str
    total_pnl: float
    trade_count: int

class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]

# --- API Endpoints ---
@app.on_event("startup")
async def startup_event():
    # Initialize ZScore trackers for all known symbols from config
    # This pre-populates them, so they start accumulating data if your design implies that.
    # Alternatively, create them on-demand in the endpoint.
    if SYMBOLS:
        for sym in SYMBOLS:
            if sym not in zscore_trackers:
                zscore_trackers[sym] = RollingZScore(window_size=DEFAULT_ZSCORE_WINDOW)
    logger.info("FastAPI application startup complete.")
    if data_provider.error:
        logger.warning(f"WARNING during startup: DataProvider had an initialization error: {data_provider.error}")

@app.get("/api/v1/market_data/all", response_model=MarketDataAllResponse)
async def get_market_data_all():
    """
    Return latest market data (including Z-score) for all symbols.
    """
    result = {}
    for symbol in SYMBOLS:
        books = data_provider.get_top_of_book(symbol)
        current_ts = pd.Timestamp.utcnow()
        if not books:
            result[symbol] = MarketDataResponse(
                timestamp=current_ts.isoformat(),
                symbol=symbol,
                binance=BookLevel(bid=0, ask=0),
                kraken=BookLevel(bid=0, ask=0),
                spread=0,
                error="Failed to fetch books."
            )
            continue
        bid_bin, ask_bin = books['binance']['bid'], books['binance']['ask']
        bid_kr, ask_kr = books['kraken']['bid'], books['kraken']['ask']
        spread = ask_bin - bid_kr
        if symbol not in zscore_trackers:
            zscore_trackers[symbol] = RollingZScore(window_size=DEFAULT_ZSCORE_WINDOW)
        z_tracker = zscore_trackers[symbol]
        current_z_score = z_tracker.add(spread)
        result[symbol] = MarketDataResponse(
            timestamp=current_ts.isoformat(),
            symbol=symbol,
            binance=BookLevel(bid=bid_bin, ask=ask_bin),
            kraken=BookLevel(bid=bid_kr, ask=ask_kr),
            spread=spread,
            z_score=current_z_score
        )
    return MarketDataAllResponse(data=result)

@app.get("/api/v1/market_data/{symbol:path}", response_model=MarketDataResponse)
async def get_market_data(symbol: str = Path(..., title="The symbol for the market data, e.g., BTC/USDT")):
    """
    Fetch the latest top-of-book market data, spread, and Z-score for a given symbol.
    Checks for stop-loss conditions before checking for new trade entries.
    Simulates trades based on Z-score if conditions are met.
    """
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not configured or supported.")

    current_ts = pd.Timestamp.utcnow()
    books = data_provider.get_top_of_book(symbol)

    if data_provider.error:
        return MarketDataResponse(
            timestamp=current_ts.isoformat(),
            symbol=symbol,
            binance=BookLevel(bid=0, ask=0),
            kraken=BookLevel(bid=0, ask=0),
            spread=0,
            error=f"DataProvider error: {data_provider.error}"
        )
    if not books:
        return MarketDataResponse(
            timestamp=current_ts.isoformat(),
            symbol=symbol,
            binance=BookLevel(bid=0, ask=0),
            kraken=BookLevel(bid=0, ask=0),
            spread=0,
            error="Failed to fetch books, no specific error from provider."
        )

    bid_bin, ask_bin = books['binance']['bid'], books['binance']['ask']
    bid_kr, ask_kr   = books['kraken']['bid'],  books['kraken']['ask']
    spread = ask_bin - bid_kr  # Current spread

    # Get or create ZScore tracker for the symbol
    if symbol not in zscore_trackers:
        zscore_trackers[symbol] = RollingZScore(window_size=DEFAULT_ZSCORE_WINDOW)
    z_tracker = zscore_trackers[symbol]
    current_z_score = z_tracker.add(spread)

    # --- New Arbitrage Logic: Spread-based ---
    now = time.time()
    min_spread = MIN_SPREAD_PCT * ((ask_bin + bid_kr) / 2)
    can_trade_now = (now - last_trade_time[symbol]) > TRADE_COOLDOWN_SEC
    entry_signal = False
    trade_direction = 0
    pnl = 0.0
    entry_spread_for_trade = spread

    # Debug logging for spread calculations
    logger.info(f"[{symbol}] Spread: {spread:.6f}, min_spread: {min_spread:.6f}, ask_bin: {ask_bin}, bid_kr: {bid_kr}, bid_bin: {bid_bin}, ask_kr: {ask_kr}")

    # Only consider entry if we don't have an active position and cooldown passed
    if risk_manager.last_entry_spread is None and can_trade_now:
        spread1 = bid_bin - ask_kr
        spread2 = bid_kr - ask_bin
        fee_bin = FEES['binance']['taker']
        fee_kr = FEES['kraken']['taker']
        eff_spread1 = spread1 - (ask_kr * fee_kr + bid_bin * fee_bin)
        eff_spread2 = spread2 - (ask_bin * fee_bin + bid_kr * fee_kr)
        logger.info(f"[{symbol}] spread1: {spread1:.6f}, eff_spread1: {eff_spread1:.6f}, spread2: {spread2:.6f}, eff_spread2: {eff_spread2:.6f}")
        if eff_spread1 > min_spread:
            entry_signal = True
            trade_direction = 1
            pnl = simulator.simulate_trade(symbol=symbol, buy_exchange='kraken', buy_price=ask_kr, sell_exchange='binance', sell_price=bid_bin, amount=TRADE_AMOUNT)
        elif eff_spread2 > min_spread:
            entry_signal = True
            trade_direction = -1
            pnl = simulator.simulate_trade(symbol=symbol, buy_exchange='binance', buy_price=ask_bin, sell_exchange='kraken', sell_price=bid_kr, amount=TRADE_AMOUNT)
        if entry_signal:
            risk_manager.register_trade(TRADE_AMOUNT, pnl, entry_spread=entry_spread_for_trade, direction=trade_direction)
            last_trade_time[symbol] = now
            logger.info(f"SPREAD ARB TRADE: {symbol}, Spread={spread:.4f}, EffSpread1={eff_spread1:.4f}, EffSpread2={eff_spread2:.4f}, PnL={pnl:.6f}, Dir={trade_direction}")

    # --- Check for Exit Conditions or Stop-Loss ---
    exit_condition_met = False
    if risk_manager.last_entry_spread is not None:
        stop_loss_hit = risk_manager.check_stop_loss(current_spread=spread)
        if stop_loss_hit:
            logger.info(f"STOP-LOSS triggered for {symbol} at spread {spread:.4f}. Risk state reset.")
            exit_condition_met = True
        else:
            # Mean reversion exit (optional, can be based on spread or Z-score)
            if risk_manager.last_trade_direction == 1 and current_z_score < EXIT_Z_THRESHOLD:
                logger.info(f"EXIT Condition (Mean Reversion) met for {symbol} (Short Spread Entry). Z={current_z_score:.2f} < {EXIT_Z_THRESHOLD}. Resetting risk state.")
                risk_manager.reset_entry_state()
                exit_condition_met = True
            elif risk_manager.last_trade_direction == -1 and current_z_score > -EXIT_Z_THRESHOLD:
                logger.info(f"EXIT Condition (Mean Reversion) met for {symbol} (Long Spread Entry). Z={current_z_score:.2f} > {-EXIT_Z_THRESHOLD}. Resetting risk state.")
                risk_manager.reset_entry_state()
                exit_condition_met = True

    return MarketDataResponse(
        timestamp=current_ts.isoformat(),
        symbol=symbol,
        binance=BookLevel(bid=bid_bin, ask=ask_bin),
        kraken=BookLevel(bid=bid_kr, ask=ask_kr),
        spread=spread,
        z_score=current_z_score
    )

@app.get("/api/v1/simulation/status", response_model=SimulationStatusResponse)
async def get_simulation_status():
    """
    Get the current status of the trade simulation (e.g., PnL, total trades).
    """
    return SimulationStatusResponse(
        total_pnl=simulator.total_pnl,
        total_trades=len(simulator.trades),
        # Include the parameters used in the logic
        z_score_threshold=Z_SCORE_THRESHOLD,
        trade_amount=TRADE_AMOUNT,
        exit_z_threshold=EXIT_Z_THRESHOLD,
        stop_loss_amount=STOP_LOSS_AMOUNT
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
            # Add other potential types if necessary (e.g., datetime.datetime)

        except Exception as e:
            logger.error(f"Error formatting timestamp '{trade_timestamp}': {e}")
            # timestamp_str remains "Invalid Timestamp"

        recent_trades.append(TradeDetail(
            timestamp=timestamp_str,
            symbol=trade_dict.get('symbol', 'N/A'),
            buy_exchange=trade_dict.get('buy_exchange', 'N/A'),
            buy_price=trade_dict.get('buy_price', 0.0),
            sell_exchange=trade_dict.get('sell_exchange', 'N/A'),
            sell_price=trade_dict.get('sell_price', 0.0),
            amount=trade_dict.get('amount', 0.0),
            pnl=trade_dict.get('pnl', 0.0)
        ))
    return RecentTradesResponse(trades=recent_trades)

# New endpoint for Sentiment (Placeholder)
@app.get("/api/v1/sentiment/{symbol:path}", response_model=SentimentResponse)
async def get_sentiment(symbol: str = Path(..., title="The symbol to get sentiment for, e.g., BTC/USDT")):
    """
    Placeholder endpoint for fetching news sentiment for a given symbol.
    Currently returns a static neutral sentiment.
    """
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Sentiment analysis not available or symbol '{symbol}' not supported.")
    
    # In a real implementation, this would:
    # 1. Fetch recent news/social media related to the symbol.
    # 2. Call OpenAI API (or other model) to get sentiment.
    # 3. Cache the result with a reasonable TTL.
    
    return SentimentResponse(
        symbol=symbol,
        sentiment_label="neutral", # Placeholder
        sentiment_score=0.0,       # Placeholder
        source="placeholder",
        timestamp=pd.Timestamp.utcnow().isoformat(timespec='milliseconds').replace('+00:00', 'Z') # Current time
    )

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

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Crypto HFT Tool API. Visit /docs for API documentation."}

# To run the server (save this as main.py in src/crypto_hft_tool/):
# Ensure your terminal is in the root of your project (crypto_hft_tool folder, not src)
# Then run: uvicorn src.crypto_hft_tool.main:app --reload --port 8000