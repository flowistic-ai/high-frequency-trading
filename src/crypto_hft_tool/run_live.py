import asyncio
import signal
from typing import Optional
from datetime import datetime

from .live_trader import LiveTrader
from .utils.logging_config import setup_logging, get_logger

logger = get_logger(__name__)

class TradingManager:
    def __init__(self):
        self.trader: Optional[LiveTrader] = None
        self.should_run = True
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown"""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)
            
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}. Initiating shutdown...")
        self.should_run = False
        
    async def _print_metrics(self):
        """Periodically print trading metrics"""
        while self.should_run:
            if self.trader and self.trader.metrics:
                metrics = self.trader.metrics
                logger.info("\n=== Trading Metrics ===")
                logger.info(f"Total PnL: {metrics['total_pnl']:.8f}")
                logger.info(f"Open PnL: {metrics['open_pnl']:.8f}")
                logger.info(f"Total Trades: {metrics['trades_count']}")
                logger.info(f"Error Count: {metrics['errors_count']}")
                
                # Calculate average latency
                if metrics['latency_ms']:
                    avg_latency = sum(metrics['latency_ms']) / len(metrics['latency_ms'])
                    logger.info(f"Average Latency: {avg_latency:.2f}ms")
                
                # Print fees
                total_fees = sum(
                    sum(fees.values()) 
                    for exchange_fees in metrics['fees_paid'].values()
                    for fees in [exchange_fees]
                )
                logger.info(f"Total Fees: {total_fees:.8f}")
                
            await asyncio.sleep(60)  # Print metrics every minute
            
    async def run(self):
        """Run the trading system"""
        try:
            self.trader = LiveTrader()
            
            # Start metrics printing task
            metrics_task = asyncio.create_task(self._print_metrics())
            
            # Start trading
            await self.trader.run()
            
        except Exception as e:
            logger.error(f"Error in trading system: {str(e)}")
            raise
        finally:
            if self.trader:
                await self.trader.shutdown()
            
            # Cancel metrics task
            if 'metrics_task' in locals():
                metrics_task.cancel()
                try:
                    await metrics_task
                except asyncio.CancelledError:
                    pass

def main():
    # Configure logging using centralized setup
    setup_logging(
        level='INFO',
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        log_file=f"logs/live_trading_{datetime.now():%Y%m%d_%H%M%S}.log"
    )
    
    # Create and run trading manager
    manager = TradingManager()
    
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise
    finally:
        logger.info("Trading system shutdown complete.")

if __name__ == "__main__":
    main() 