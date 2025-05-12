import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .signals import RollingZScore
from .simulation import TradeSimulator
from .risk_manager import RiskManager
from .config import SYMBOLS, data_folder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Backtester:
    def __init__(
        self,
        data_dir: str = f"{data_folder}/processed",
        window_size: int = 200,
        zscore_threshold: float = 2.0,
        trade_amount: float = 0.001
    ):
        self.data_dir = Path(data_dir)
        self.window_size = window_size
        self.zscore_threshold = zscore_threshold
        self.trade_amount = trade_amount
        
        # Initialize components
        self.simulator = TradeSimulator()
        self.risk_manager = RiskManager()
        self.ztrackers = {sym: RollingZScore(window_size) for sym in SYMBOLS}
        
        # Performance metrics
        self.metrics = {
            'total_pnl': 0.0,
            'win_count': 0,
            'loss_count': 0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'peak_value': 0.0,
            'trades_per_symbol': {sym: 0 for sym in SYMBOLS},
            'trade_pnls': [],  # List to store individual trade PnLs
            'cumulative_pnls': [],  # List to store cumulative PnL over time
            'sharpe_ratio': 0.0,
            'avg_trade_pnl': 0.0,
            'std_trade_pnl': 0.0
        }

    def calculate_performance_metrics(self):
        """Calculate advanced performance metrics."""
        if not self.metrics['trade_pnls']:
            return
        
        # Convert to numpy arrays for calculations
        trade_pnls = np.array(self.metrics['trade_pnls'])
        cumulative_pnls = np.array(self.metrics['cumulative_pnls'])
        
        # Basic metrics
        total_trades = len(trade_pnls)
        win_rate = (self.metrics['win_count'] / total_trades * 100) if total_trades > 0 else 0
        
        # Average and standard deviation of trade PnLs
        avg_pnl = np.mean(trade_pnls)
        std_pnl = np.std(trade_pnls)
        
        # Sharpe Ratio (annualized)
        if std_pnl > 0:
            sharpe = (avg_pnl / std_pnl) * np.sqrt(total_trades)
        else:
            sharpe = 0.0
        
        # Maximum Drawdown
        peak = np.maximum.accumulate(cumulative_pnls)
        drawdown = peak - cumulative_pnls
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
        
        # Update metrics
        self.metrics.update({
            'sharpe_ratio': sharpe,
            'avg_trade_pnl': avg_pnl,
            'std_trade_pnl': std_pnl,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate
        })

    def load_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load processed historical data for a symbol."""
        try:
            file_path = self.data_dir / f"{symbol.replace('/', '_')}.csv"
            if not file_path.exists():
                logger.error(f"Data file not found: {file_path}")
                return None
            
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {str(e)}")
            return None

    def calculate_spread(self, row: pd.Series) -> float:
        """Calculate spread between exchanges."""
        return row['binance_ask'] - row['kraken_bid']

    def run_backtest(self, symbol: str) -> Dict:
        """Run backtest for a single symbol."""
        # Load data
        df = self.load_data(symbol)
        if df is None:
            return self.metrics

        logger.info(f"Backtesting {symbol} on {len(df)} rows")
        
        # Track entry spread for stop-loss
        entry_spread = None
        in_trade = False
        
        # Process each row
        for _, row in df.iterrows():
            # Calculate spread and Z-score
            spread = self.calculate_spread(row)
            z = self.ztrackers[symbol].add(spread)
            
            # Check for trading signals
            if abs(z) >= self.zscore_threshold and not in_trade:
                # Check if risk manager allows the trade
                if not self.risk_manager.can_trade(symbol, self.trade_amount):
                    logger.info(f"RiskManager blocked trade for {symbol}")
                    continue
                
                # Record entry spread
                entry_spread = spread
                in_trade = True
                
                # Simulate trade
                if z > 0:
                    # Sell on Binance, buy on Kraken
                    pnl = self.simulator.simulate_trade(
                        symbol,
                        buy_exchange='kraken',
                        buy_price=row['kraken_ask'],
                        sell_exchange='binance',
                        sell_price=row['binance_bid'],
                        amount=self.trade_amount
                    )
                else:
                    # Buy on Binance, sell on Kraken
                    pnl = self.simulator.simulate_trade(
                        symbol,
                        buy_exchange='binance',
                        buy_price=row['binance_ask'],
                        sell_exchange='kraken',
                        sell_price=row['kraken_bid'],
                        amount=self.trade_amount
                    )
                
                # Update metrics
                self.metrics['total_pnl'] += pnl
                self.metrics['trades_per_symbol'][symbol] += 1
                self.metrics['trade_pnls'].append(pnl)
                self.metrics['cumulative_pnls'].append(self.metrics['total_pnl'])
                
                if pnl > 0:
                    self.metrics['win_count'] += 1
                else:
                    self.metrics['loss_count'] += 1
                
                # Register trade with risk manager
                self.risk_manager.register_trade(self.trade_amount, pnl)
                
                logger.info(f"Trade executed at {row['timestamp']}: PnL = {pnl:.8f}")
            
            # Check stop-loss if in trade
            elif in_trade and self.risk_manager.check_stop_loss(entry_spread, spread):
                logger.info(f"Stop-loss triggered at {row['timestamp']}")
                in_trade = False
                entry_spread = None
        
        # Calculate final performance metrics
        self.calculate_performance_metrics()
        return self.metrics

    def run_all(self):
        """Run backtest for all configured symbols."""
        for symbol in SYMBOLS:
            logger.info(f"\nBacktesting {symbol}...")
            self.run_backtest(symbol)
            self.print_results(symbol)
        
        # Print overall results
        self.print_results()

    def print_results(self, symbol: Optional[str] = None):
        """Print backtest results for a specific symbol or overall."""
        if symbol:
            print(f"\n=== {symbol} Results ===")
            print(f"Trades: {self.metrics['trades_per_symbol'][symbol]}")
        else:
            total_trades = self.metrics['win_count'] + self.metrics['loss_count']
            print("\n=== Overall Results ===")
            print(f"Total PnL: {self.metrics['total_pnl']:.8f}")
            print(f"Win Rate: {self.metrics['win_rate']:.2f}%")
            print(f"Total Trades: {total_trades}")
            print(f"Average Trade PnL: {self.metrics['avg_trade_pnl']:.8f}")
            print(f"PnL Std Dev: {self.metrics['std_trade_pnl']:.8f}")
            print(f"Sharpe Ratio: {self.metrics['sharpe_ratio']:.2f}")
            print(f"Max Drawdown: {self.metrics['max_drawdown']:.8f}")
            print("\nTrades per Symbol:")
            for sym, count in self.metrics['trades_per_symbol'].items():
                print(f"{sym}: {count}")

if __name__ == "__main__":
    # Usage: python -m crypto_hft_tool.backtest
    backtester = Backtester()
    backtester.run_all() 