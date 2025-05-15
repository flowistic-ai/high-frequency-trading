import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from .signals import RollingZScore
from .risk_manager import RiskManager
from .fee_manager import FeeManager
from .orderbook_manager import OrderbookManager
from .config import (
    SYMBOLS, ZSCORE_SETTINGS, TRADE_SETTINGS,
    RISK_SETTINGS, EXCHANGE_CREDENTIALS
)
from .enhanced_signals import EnhancedSignalProcessor
from .execution_manager import ExecutionManager
from .enhanced_risk_manager import EnhancedRiskManager

logger = logging.getLogger(__name__)

class LiveTrader:
    def __init__(self, max_workers: int = 4):
        # Initialize components
        self.risk_manager = EnhancedRiskManager(
            base_position_sizes=TRADE_SETTINGS['position_sizing']['min_size'],
            max_position_values=RISK_SETTINGS['max_position_value'],
            drawdown_limits=RISK_SETTINGS['max_drawdown'],
            volatility_lookback=300,  # 5 minutes
            correlation_lookback=900,  # 15 minutes
            risk_free_rate=0.0
        )
        self.fee_manager = FeeManager()
        self.orderbook_manager = OrderbookManager()
        self.execution_manager = ExecutionManager(
            fee_manager=self.fee_manager,
            min_liquidity_ratio=TRADE_SETTINGS['execution'].get('min_liquidity_ratio', 0.3),
            max_price_impact=TRADE_SETTINGS['execution'].get('max_price_impact', 0.0001),
            iceberg_threshold=TRADE_SETTINGS['execution'].get('iceberg_threshold', 1.0),
            min_fill_ratio=TRADE_SETTINGS['execution'].get('min_fill_ratio', 0.95)
        )
        
        # Initialize exchange clients
        self.exchanges = {}
        self._init_exchange_clients()
        
        # Initialize signal processors with pre-allocated numpy arrays
        self.signal_processors = {
            sym: EnhancedSignalProcessor(
                base_windows=ZSCORE_SETTINGS['windows'],
                momentum_window=ZSCORE_SETTINGS.get('momentum_window', 20),
                correlation_window=ZSCORE_SETTINGS.get('correlation_window', 50),
                vol_window=ZSCORE_SETTINGS.get('vol_window', 30),
                min_threshold=ZSCORE_SETTINGS['thresholds']['entry']['min'],
                max_threshold=ZSCORE_SETTINGS['thresholds']['entry']['max'],
                vol_impact=ZSCORE_SETTINGS.get('vol_impact', 0.3)
            ) for sym in SYMBOLS
        }
        
        # Active positions tracking with numpy arrays for fast calculations
        self.positions = {sym: {} for sym in SYMBOLS}
        self.last_trade_time = {sym: None for sym in SYMBOLS}
        
        # Performance metrics with numpy arrays
        self.metrics = {
            'total_pnl': 0.0,
            'open_pnl': 0.0,
            'trades_count': 0,
            'errors_count': 0,
            'latency_ms': np.array([], dtype=np.float64),
            'fees_paid': {
                'binance': {'maker': 0.0, 'taker': 0.0},
                'kraken': {'maker': 0.0, 'taker': 0.0}
            },
            'signal_metrics': {
                'avg_strength': 0.0,
                'false_signals': 0,
                'true_signals': 0,
                'volatility': np.array([], dtype=np.float64)
            },
            'risk_metrics': {}  # Will be updated from risk manager
        }
        
        # Batch processing settings
        self.batch_size = 100
        self.update_queue = asyncio.Queue()

    async def _init_exchange_clients(self):
        """Initialize exchange API clients with error handling"""
        try:
            from ccxt.async_support import binance, kraken
            
            self.exchanges['binance'] = binance({
                'apiKey': EXCHANGE_CREDENTIALS['binance']['apiKey'],
                'secret': EXCHANGE_CREDENTIALS['binance']['secret'],
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            
            self.exchanges['kraken'] = kraken({
                'apiKey': EXCHANGE_CREDENTIALS['kraken']['apiKey'],
                'secret': EXCHANGE_CREDENTIALS['kraken']['secret'],
                'enableRateLimit': True
            })
            
            # Test API connections
            await self._test_exchange_connections()
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange clients: {str(e)}")
            raise

    async def _test_exchange_connections(self):
        """Test exchange API connections"""
        for name, exchange in self.exchanges.items():
            try:
                await exchange.load_markets()
                balance = await exchange.fetch_balance()
                logger.info(f"Successfully connected to {name}")
                logger.info(f"Available balance: {balance['free']}")
            except Exception as e:
                logger.error(f"Failed to connect to {name}: {str(e)}")
                raise

    def _calculate_trade_metrics(self, symbol: str, books: Dict[str, Dict]) -> Optional[Dict]:
        """Calculate trade metrics in a separate thread"""
        try:
            spread = books['binance']['ask'] - books['kraken']['bid']
            timestamp = datetime.now()
            
            # Skip if minimum trade interval not met
            if (self.last_trade_time[symbol] and 
                (timestamp - self.last_trade_time[symbol]).total_seconds() < 
                TRADE_SETTINGS['execution']['min_trade_interval']):
                return None

            # Calculate spread metrics
            avg_price = (books['binance']['ask'] + books['kraken']['bid']) / 2
            spread_ratio = abs(float(spread)) / float(avg_price)
            
            if not (TRADE_SETTINGS['thresholds']['min_spread_ratio'] <= 
                    spread_ratio <= 
                    TRADE_SETTINGS['thresholds']['max_spread_ratio']):
                return None

            # Get enhanced signals
            volume = (float(books['binance']['ask']) * float(books['binance'].get('askVolume', 1)) +
                     float(books['kraken']['bid']) * float(books['kraken'].get('bidVolume', 1))) / 2
            
            signals = self.signal_processors[symbol].update(float(spread), volume, timestamp)
            
            # Find strongest signal
            strongest_signal = max(
                signals.values(),
                key=lambda x: x.signal_strength
            )
            
            # Update metrics
            self.metrics['signal_metrics']['volatility'] = np.append(
                self.metrics['signal_metrics']['volatility'],
                strongest_signal.volatility
            )
            
            # Check if signal meets threshold
            if strongest_signal.signal_strength < strongest_signal.threshold:
                self.metrics['signal_metrics']['false_signals'] += 1
                return None
                
            self.metrics['signal_metrics']['true_signals'] += 1
            self.metrics['signal_metrics']['avg_strength'] = (
                (self.metrics['signal_metrics']['avg_strength'] * 
                 self.metrics['signal_metrics']['true_signals'] +
                 strongest_signal.signal_strength) /
                (self.metrics['signal_metrics']['true_signals'] + 1)
            )

            # Determine trade direction and profitability
            direction = 1 if strongest_signal.zscore > 0 else -1
            
            if direction > 0:  # Expect spread to decrease
                profit = float(books['binance']['bid']) - float(books['kraken']['ask'])
            else:  # Expect spread to increase
                profit = float(books['kraken']['bid']) - float(books['binance']['ask'])

            min_profit = TRADE_SETTINGS['thresholds']['min_profit_after_fees'].get(
                symbol, TRADE_SETTINGS['thresholds']['min_profit_after_fees']['default']
            )
            
            if profit < min_profit:
                return None

            return {
                'signal': strongest_signal,
                'direction': direction,
                'profit': profit,
                'timestamp': timestamp
            }
            
        except Exception as e:
            logger.error(f"Error calculating trade metrics for {symbol}: {e}")
            return None

    async def _process_trade_opportunities(self):
        """Process trade opportunities in batches"""
        while True:
            try:
                # Collect updates in batches
                updates = []
                try:
                    while len(updates) < self.batch_size:
                        update = await asyncio.wait_for(
                            self.update_queue.get(), 
                            timeout=0.1
                        )
                        updates.append(update)
                except asyncio.TimeoutError:
                    if not updates:
                        continue

                # Process updates in parallel
                tasks = []
                for symbol, books in updates:
                    if not self.positions[symbol]:  # Only process if no active position
                        task = self.executor.submit(
                            self._calculate_trade_metrics, 
                            symbol, 
                            books
                        )
                        tasks.append((symbol, books, task))

                # Execute valid trades
                for symbol, books, task in tasks:
                    try:
                        trade_params = task.result()
                        if trade_params:
                            # Get optimal position size from risk manager
                            can_trade, size = self.risk_manager.can_trade(
                                symbol,
                                float(books['binance']['ask']),
                                float(books['binance'].get('askVolume', 1.0))
                            )
                            
                            if can_trade and size > 0:
                                await self._execute_trade(
                                    symbol,
                                    trade_params,
                                    books,
                                    size
                                )
                    except Exception as e:
                        logger.error(f"Error processing trade for {symbol}: {e}")
                        self.metrics['errors_count'] += 1
                        
                # Update risk metrics
                self.metrics['risk_metrics'] = self.risk_manager.get_portfolio_metrics()

            except Exception as e:
                logger.error(f"Error in trade processing loop: {e}")
                await asyncio.sleep(1)

    async def _execute_trade(
        self,
        symbol: str,
        trade_params: Dict,
        books: Dict[str, Dict],
        size: float
    ) -> bool:
        """Execute trade across exchanges with smart routing"""
        direction = trade_params['direction']
        
        try:
            if direction > 0:  # Sell on Binance, buy on Kraken
                # Execute orders with smart routing
                sell_order = await self.execution_manager.execute_order(
                    'binance',
                    self.exchanges['binance'],
                    symbol,
                    'sell',
                    size,
                    books['binance']
                )
                
                if not sell_order:
                    logger.error("Failed to execute sell order on Binance")
                    return False
                
                buy_order = await self.execution_manager.execute_order(
                    'kraken',
                    self.exchanges['kraken'],
                    symbol,
                    'buy',
                    size,
                    books['kraken']
                )
                
                if not buy_order:
                    # Try to cancel sell order
                    try:
                        await self.exchanges['binance'].cancel_order(
                            sell_order['id'], symbol
                        )
                    except Exception as e:
                        logger.error(f"Error canceling Binance order: {e}")
                    return False
                
            else:  # Buy on Binance, sell on Kraken
                buy_order = await self.execution_manager.execute_order(
                    'binance',
                    self.exchanges['binance'],
                    symbol,
                    'buy',
                    size,
                    books['binance']
                )
                
                if not buy_order:
                    logger.error("Failed to execute buy order on Binance")
                    return False
                
                sell_order = await self.execution_manager.execute_order(
                    'kraken',
                    self.exchanges['kraken'],
                    symbol,
                    'sell',
                    size,
                    books['kraken']
                )
                
                if not sell_order:
                    # Try to cancel buy order
                    try:
                        await self.exchanges['binance'].cancel_order(
                            buy_order['id'], symbol
                        )
                    except Exception as e:
                        logger.error(f"Error canceling Binance order: {e}")
                    return False

            # Calculate realized PnL
            if direction > 0:
                realized_pnl = (
                    float(sell_order['average']) * size -
                    float(buy_order['average']) * size
                )
            else:
                realized_pnl = (
                    float(sell_order['average']) * size -
                    float(buy_order['average']) * size
                )

            # Update metrics
            self.metrics['trades_count'] += 1
            self.metrics['total_pnl'] += realized_pnl
            self.last_trade_time[symbol] = datetime.now()
            
            # Update execution metrics
            for key in ['slippage', 'fill_ratios', 'execution_times', 'price_impact']:
                if key in self.execution_manager.metrics:
                    self.metrics[f'execution_{key}'] = self.execution_manager.metrics[key]
            
            # Register trade with risk manager
            self.risk_manager.register_trade(
                symbol,
                size,
                float(buy_order['average'] if direction > 0 else sell_order['average']),
                realized_pnl
            )
            
            logger.info(
                f"Trade executed: {symbol}, Direction={direction}, "
                f"Size={size:.8f}, PnL={realized_pnl:.8f}, "
                f"Slippage={self.execution_manager.metrics['slippage'][-1]:.4%}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            self.metrics['errors_count'] += 1
            return False

    async def _execute_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        amount: float,
        price: float
    ) -> Optional[Dict]:
        """Execute order with error handling and latency tracking"""
        start_time = datetime.now()
        try:
            order = await self.exchanges[exchange].create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=amount,
                price=price
            )
            
            # Track latency using numpy array
            latency = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics['latency_ms'] = np.append(
                self.metrics['latency_ms'], 
                latency
            )
            
            logger.info(f"Order executed on {exchange}: {order}")
            return order
            
        except Exception as e:
            logger.error(f"Error executing order on {exchange}: {str(e)}")
            self.metrics['errors_count'] += 1
            return None

    async def run(self):
        """Main trading loop"""
        logger.info("Starting live trading...")
        
        # Start orderbook manager
        orderbook_task = asyncio.create_task(self.orderbook_manager.start())
        
        # Start trade processor
        processor_task = asyncio.create_task(self._process_trade_opportunities())
        
        try:
            while True:
                market_data = {}
                for symbol in SYMBOLS:
                    # Get latest orderbooks
                    books = {}
                    for exchange in ['binance', 'kraken']:
                        book = self.orderbook_manager.get_orderbook(exchange, symbol)
                        if not book:
                            continue
                        books[exchange] = book
                    
                    if len(books) == 2:
                        # Add to processing queue
                        await self.update_queue.put((symbol, books))
                        
                        # Update market data for risk manager
                        market_data[symbol] = {
                            'price': float(books['binance']['ask']),
                            'volume': float(books['binance'].get('askVolume', 1.0)),
                            'return': (
                                float(books['binance']['ask']) /
                                float(books['binance']['bid']) - 1
                            )
                        }
                
                # Update positions and check for trades to close
                if market_data:
                    trades_to_close = await self.risk_manager.update_positions(
                        market_data
                    )
                    
                    for symbol, size, price in trades_to_close:
                        logger.info(
                            f"Closing position: {symbol}, "
                            f"Size={size:.8f}, Price={price:.2f}"
                        )
                        # Implement position closing logic here
                
                await asyncio.sleep(0.1)  # Small delay to prevent CPU overload
                
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            raise
        finally:
            # Cleanup
            orderbook_task.cancel()
            processor_task.cancel()
            await self.shutdown()

    async def shutdown(self):
        """Clean shutdown of all components"""
        logger.info("Shutting down...")
        
        # Close exchange connections
        for exchange in self.exchanges.values():
            try:
                await exchange.close()
            except Exception as e:
                logger.error(f"Error closing exchange connection: {str(e)}")
                
        # Stop orderbook manager
        await self.orderbook_manager.stop()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True) 