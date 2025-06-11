import asyncio
import json
from ccxt.async_support import binance, kraken
import websockets

from .config import WS_ENDPOINTS, SYMBOLS
from .signals import RollingZScore
from .simulation import TradeSimulator
from .risk_manager import RiskManager
from .utils.logging_config import get_logger

logger = get_logger(__name__)


class OrderBookPipeline:
    def __init__(self):
        # Instantiate exchange clients with credentials
        self.exchanges = {
            "binance": binance({"enableRateLimit": True}),
            "kraken": kraken({"enableRateLimit": True}),
        }
        
        # Rolling Z-score calculators per symbol pair
        # e.g. key="BTC/USDT", value=RollingZScore(window_size=200)
        self.zscore_trackers = {
            sym: RollingZScore(window_size=100)
            for sym in SYMBOLS
        }
        # Threshold beyond which we flag a signal
        self.zscore_threshold = 1.2
        
        # Cache for latest order book state per exchange and symbol
        self.latest_book = {
            exchange: {symbol: {"bid": [None, None], "ask": [None, None], "timestamp": None}
                      for symbol in SYMBOLS}
            for exchange in self.exchanges
        }
        
        # Initialize trade simulator
        self.simulator = TradeSimulator()
        self.trade_amount = 0.001  # e.g. 0.001 BTC per trade
        
        # Initialize risk manager
        self.risk = RiskManager()

    async def fetch_snapshot(self, exchange_name: str, symbol: str):
        """Fetch REST snapshot of the order book."""
        exchange = self.exchanges[exchange_name]
        try:
            logger.info(f"Fetching initial snapshot for {symbol} on {exchange_name}")
            orderbook = await exchange.fetch_order_book(symbol)
            # grab only top-of-book for now
            top = {
                "bid": orderbook["bids"][0] if orderbook["bids"] else [None, None],
                "ask": orderbook["asks"][0] if orderbook["asks"] else [None, None],
                "timestamp": orderbook["timestamp"],
            }
            # Update cache
            self.latest_book[exchange_name][symbol] = top
            return top
        except Exception as e:
            logger.error(f"Error fetching snapshot for {symbol} on {exchange_name}: {str(e)}")
            return None

    async def subscribe_ws(self, exchange_name: str, symbol: str):
        """Subscribe to exchange's websocket for live updates."""
        uri = WS_ENDPOINTS[exchange_name]
        # Format differs per exchange; here's Binance example:
        if exchange_name == "binance":
            stream = symbol.lower().replace("/", "") + "@bookTicker"
            uri = f"{uri}/{stream}"
        elif exchange_name == "kraken":
            # Kraken uses a JSON subscribe message
            pass  # implement below
        else:
            raise ValueError("Unsupported exchange")

        try:
            async with websockets.connect(uri) as ws:
                logger.info(f"WebSocket connected to {exchange_name} for {symbol}")
                if exchange_name == "kraken":
                    subscribe_msg = {
                        "event": "subscribe",
                        "pair": [symbol.replace("/", "")],
                        "subscription": {"name": "book"}
                    }
                    await ws.send(json.dumps(subscribe_msg))

                async for message in ws:
                    data = json.loads(message)
                    # Normalize update to {"bid", "ask", "timestamp"} format
                    if exchange_name == "binance":
                        normalized = {
                            "bid": [float(data["b"]), float(data["B"])],
                            "ask": [float(data["a"]), float(data["A"])],
                            "timestamp": data["E"]
                        }
                    elif exchange_name == "kraken":
                        # TODO: Implement Kraken normalization
                        normalized = data  # Placeholder
                    
                    # Update cache
                    self.latest_book[exchange_name][symbol] = normalized
                    yield normalized
        except Exception as e:
            logger.error(f"WebSocket error for {symbol} on {exchange_name}: {str(e)}")

    async def run(self):
        """Main loop: for each exchange and symbol, log top-of-book."""
        tasks = []
        for ex in self.exchanges:
            for sym in SYMBOLS:
                # schedule snapshot + ws reader
                tasks.append(self._handle(ex, sym))
        try:
            await asyncio.gather(*tasks)
        finally:
            # Clean up exchange connections
            for exchange in self.exchanges.values():
                await exchange.close()

    async def _handle(self, exchange_name: str, symbol: str):
        # 1) fetch initial snapshots for both exchanges
        snap_other_name = "kraken" if exchange_name == "binance" else "binance"
        snap_self = await self.fetch_snapshot(exchange_name, symbol)
        snap_other = await self.fetch_snapshot(snap_other_name, symbol)

        if not snap_self or not snap_other:
            logger.error(f"Failed to get initial snapshots for {symbol}")
            return

        # Compute initial spread: ask_self – bid_other
        spread = snap_self["ask"][0] - snap_other["bid"][0]
        z = self.zscore_trackers[symbol].add(spread)
        logger.info(f"{symbol} init spread={spread:.6f}, z={z:.3f}")

        # 2) stream live updates
        async for update in self.subscribe_ws(exchange_name, symbol):
            # Get latest other-exchange top-of-book from cache
            other = self.latest_book[snap_other_name][symbol]

            # Recompute spread
            spread = update["ask"][0] - other["bid"][0]
            z = self.zscore_trackers[symbol].add(spread)

            # Log and flag if |z| > threshold
            if abs(z) >= self.zscore_threshold:
                logger.info(
                    f"⚡ SIGNAL {symbol} | spread={spread:.6f}, z={z:.3f}"
                )
                
                # Determine trade amount from config
                amount = self.trade_amount  # you can also fetch per-symbol via config

                # Check if risk manager allows this trade
                if not self.risk.can_trade(symbol, amount):
                    logger.info(f"RiskManager blocked trade for {symbol} amount={amount}")
                    continue  # skip this signal

                # Record entry spread for stop-loss check
                entry_spread = spread

                # Determine which leg is cheaper
                if z > 0:
                    # Sell on this exchange, buy on the other
                    pnl = self.simulator.simulate_trade(
                        symbol,
                        buy_exchange=snap_other_name,
                        buy_price=snap_other["ask"][0],
                        sell_exchange=exchange_name,
                        sell_price=update["bid"][0],
                        amount=amount,
                    )
                else:
                    # z < 0: buy on this exchange, sell on the other
                    pnl = self.simulator.simulate_trade(
                        symbol,
                        buy_exchange=exchange_name,
                        buy_price=update["ask"][0],
                        sell_exchange=snap_other_name,
                        sell_price=snap_self["bid"][0],
                        amount=amount,
                    )
                
                # Register trade with risk manager
                self.risk.register_trade(amount, pnl)
                logger.info(f"P&L for this trade: {pnl:.8f}")

                # Monitor stop-loss
                if self.risk.check_stop_loss(entry_spread, spread):
                    # Abort or reverse; for POC we'll just log and skip
                    logger.info("Aborting trade due to stop-loss")
                    break  # exit the update loop for this signal


if __name__ == "__main__":
    # Allow: python -m crypto_hft_tool.data_pipeline
    pipeline = OrderBookPipeline()
    try:
        asyncio.run(pipeline.run())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
