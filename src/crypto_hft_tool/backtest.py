import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .signals import RollingZScore
from .simulation import TradeSimulator
from .risk_manager import RiskManager
from .fee_manager import FeeManager
from .config import (
    SYMBOLS, data_folder, ZSCORE_SETTINGS, 
    TRADE_SETTINGS, RISK_SETTINGS
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Backtester:
    def __init__(
        self,
        data_dir: str = f"{data_folder}/processed",
        trade_amount: float = 0.001
    ):
        self.data_dir = Path(data_dir)
        self.trade_amount = trade_amount
        
        # Initialize components
        self.simulator = TradeSimulator()
        self.risk_manager = RiskManager()
        self.fee_manager = FeeManager()
        
        # Initialize Z-score trackers for each timeframe
        self.ztrackers = {
            sym: RollingZScore(
                windows=ZSCORE_SETTINGS['windows'],
                vol_adjustment=ZSCORE_SETTINGS['vol_adjustment']
            ) for sym in SYMBOLS
        }
        
        # Performance metrics
        self.metrics = {
            'total_pnl': 0.0,
            'win_count': 0,
            'loss_count': 0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'peak_value': 0.0,
            'trades_per_symbol': {sym: 0 for sym in SYMBOLS},
            'trades_per_timeframe': {tf: 0 for tf in ZSCORE_SETTINGS['windows'].keys()},
            'pnl_per_timeframe': {tf: 0.0 for tf in ZSCORE_SETTINGS['windows'].keys()},
            'trade_pnls': [],
            'cumulative_pnls': [],
            'sharpe_ratio': 0.0,
            'avg_trade_pnl': 0.0,
            'std_trade_pnl': 0.0,
            'fees_paid': {
                'binance': {'maker': 0.0, 'taker': 0.0},
                'kraken': {'maker': 0.0, 'taker': 0.0}
            }
        }
        
        # Trade tracking
        self.active_trades = {sym: {} for sym in SYMBOLS}
        self.last_trade_time = {sym: None for sym in SYMBOLS}

    def _check_trade_conditions(
        self, 
        symbol: str, 
        z_scores: Dict[str, float],
        spread: float,
        timestamp: datetime,
        prices: Dict[str, Dict[str, float]]
    ) -> Optional[Dict]:
        """
        Check if trade conditions are met across timeframes
        Returns trade parameters if conditions are met, None otherwise
        """
        logger.debug(f"Checking trade conditions for {symbol}")
        logger.debug(f"Current prices: {prices}")
        
        # Check minimum trade interval
        if (self.last_trade_time[symbol] and 
            (timestamp - self.last_trade_time[symbol]).total_seconds() < 
            TRADE_SETTINGS['execution']['min_trade_interval']):
            logger.debug("Trade rejected: Minimum trade interval not met")
            return None

        # Check spread thresholds
        avg_price = (prices['binance']['ask'] + prices['kraken']['bid']) / 2
        spread_ratio = abs(spread) / avg_price
        
        logger.debug(f"Spread ratio: {spread_ratio:.6f}, min: {TRADE_SETTINGS['thresholds']['min_spread_ratio']}, "
                    f"max: {TRADE_SETTINGS['thresholds']['max_spread_ratio']}")
        
        if spread_ratio < TRADE_SETTINGS['thresholds']['min_spread_ratio']:
            logger.debug("Trade rejected: Spread ratio too small")
            return None
        if spread_ratio > TRADE_SETTINGS['thresholds']['max_spread_ratio']:
            logger.debug("Trade rejected: Spread ratio too large")
            return None

        # Check z-scores across timeframes
        trade_signals = []
        logger.debug("Z-scores by timeframe:")
        for timeframe, z_score in z_scores.items():
            threshold = ZSCORE_SETTINGS['thresholds']['entry'][timeframe]
            logger.debug(f"  {timeframe}: z={z_score:.2f}, threshold={threshold}")
            if abs(z_score) >= threshold:
                trade_signals.append((timeframe, z_score))

        if not trade_signals:
            logger.debug("Trade rejected: No timeframe met z-score threshold")
            return None

        # Use the strongest signal
        timeframe, z_score = max(trade_signals, key=lambda x: abs(x[1]))
        logger.debug(f"Selected signal: {timeframe} with z-score {z_score:.2f}")
        
        # Calculate effective prices including fees
        buy_price_binance = self.fee_manager.calculate_effective_price(
            prices['binance']['ask'], 'binance', True, False)
        sell_price_binance = self.fee_manager.calculate_effective_price(
            prices['binance']['bid'], 'binance', False, False)
        buy_price_kraken = self.fee_manager.calculate_effective_price(
            prices['kraken']['ask'], 'kraken', True, False)
        sell_price_kraken = self.fee_manager.calculate_effective_price(
            prices['kraken']['bid'], 'kraken', False, False)

        logger.debug(f"Effective prices after fees:")
        logger.debug(f"  Binance: buy={buy_price_binance:.2f}, sell={sell_price_binance:.2f}")
        logger.debug(f"  Kraken: buy={buy_price_kraken:.2f}, sell={sell_price_kraken:.2f}")

        # Determine trade direction and profitability
        if z_score > 0:  # Expect spread to decrease
            profit = sell_price_binance - buy_price_kraken
            direction = 1
            logger.debug(f"Long opportunity: sell on Binance ({sell_price_binance:.2f}), "
                        f"buy on Kraken ({buy_price_kraken:.2f})")
        else:  # Expect spread to increase
            profit = sell_price_kraken - buy_price_binance
            direction = -1
            logger.debug(f"Short opportunity: sell on Kraken ({sell_price_kraken:.2f}), "
                        f"buy on Binance ({buy_price_binance:.2f})")

        min_profit = TRADE_SETTINGS['thresholds']['min_profit_after_fees'].get(
            symbol, TRADE_SETTINGS['thresholds']['min_profit_after_fees']['default']
        )
        
        logger.debug(f"Calculated profit: {profit:.8f}, minimum required: {min_profit}")

        if profit < min_profit:
            logger.debug("Trade rejected: Insufficient profit after fees")
            return None

        logger.debug("Trade conditions met, returning parameters")
        return {
            'timeframe': timeframe,
            'z_score': z_score,
            'direction': direction,
            'profit': profit
        }

    def _execute_trade(
        self,
        symbol: str,
        trade_params: Dict,
        prices: Dict[str, Dict[str, float]],
        timestamp: datetime
    ) -> float:
        """Execute trade and update metrics"""
        direction = trade_params['direction']
        pnl = 0.0

        if direction > 0:  # Sell on Binance, buy on Kraken
            pnl = self.simulator.simulate_trade(
                symbol=symbol,
                buy_exchange='kraken',
                buy_price=prices['kraken']['ask'],
                sell_exchange='binance',
                sell_price=prices['binance']['bid'],
                amount=self.trade_amount
            )
            # Record fees
            self.metrics['fees_paid']['kraken']['taker'] += self.fee_manager.estimate_fees(
                'kraken', self.trade_amount, prices['kraken']['ask'])
            self.metrics['fees_paid']['binance']['taker'] += self.fee_manager.estimate_fees(
                'binance', self.trade_amount, prices['binance']['bid'])
        else:  # Buy on Binance, sell on Kraken
            pnl = self.simulator.simulate_trade(
                symbol=symbol,
                buy_exchange='binance',
                buy_price=prices['binance']['ask'],
                sell_exchange='kraken',
                sell_price=prices['kraken']['bid'],
                amount=self.trade_amount
            )
            # Record fees
            self.metrics['fees_paid']['binance']['taker'] += self.fee_manager.estimate_fees(
                'binance', self.trade_amount, prices['binance']['ask'])
            self.metrics['fees_paid']['kraken']['taker'] += self.fee_manager.estimate_fees(
                'kraken', self.trade_amount, prices['kraken']['bid'])

        # Update metrics
        self.metrics['total_pnl'] += pnl
        self.metrics['trades_per_symbol'][symbol] += 1
        self.metrics['trades_per_timeframe'][trade_params['timeframe']] += 1
        self.metrics['pnl_per_timeframe'][trade_params['timeframe']] += pnl
        self.metrics['trade_pnls'].append(pnl)
        self.metrics['cumulative_pnls'].append(self.metrics['total_pnl'])

        if pnl > 0:
            self.metrics['win_count'] += 1
        else:
            self.metrics['loss_count'] += 1

        # Update trade tracking
        self.last_trade_time[symbol] = timestamp
        
        # Update volume history for fee calculations
        avg_price = (prices['binance']['ask'] + prices['kraken']['bid']) / 2
        self.fee_manager.add_volume('binance', self.trade_amount, avg_price, timestamp)
        self.fee_manager.add_volume('kraken', self.trade_amount, avg_price, timestamp)

        return pnl

    def run_backtest(self, symbol: str) -> Dict:
        """Run backtest for a single symbol."""
        # Load data
        df = self.load_data(symbol)
        if df is None:
            return self.metrics

        logger.info(f"Backtesting {symbol} on {len(df)} rows")
        
        for _, row in df.iterrows():
            timestamp = pd.to_datetime(row['timestamp'])
            
            # Current prices
            prices = {
                'binance': {'bid': row['binance_bid'], 'ask': row['binance_ask']},
                'kraken': {'bid': row['kraken_bid'], 'ask': row['kraken_ask']}
            }
            
            # Calculate spread and z-scores
            spread = row['binance_ask'] - row['kraken_bid']
            z_scores = self.ztrackers[symbol].add(spread, timestamp)
            
            # Check for trade opportunities
            if not self.active_trades[symbol]:
                trade_params = self._check_trade_conditions(
                    symbol, z_scores, spread, timestamp, prices
                )
                
                if trade_params and self.risk_manager.can_trade(symbol, self.trade_amount):
                    pnl = self._execute_trade(symbol, trade_params, prices, timestamp)
                    self.risk_manager.register_trade(
                        self.trade_amount, pnl, spread, trade_params['direction']
                    )
                    logger.info(
                        f"Trade executed at {timestamp}: Symbol={symbol}, "
                        f"Timeframe={trade_params['timeframe']}, Z={trade_params['z_score']:.2f}, "
                        f"PnL={pnl:.8f}"
                    )
            
            # Check exit conditions for active trades
            elif self.risk_manager.check_stop_loss(spread):
                logger.info(f"Stop-loss triggered for {symbol} at {timestamp}")
                self.risk_manager.reset_entry_state()

        # Calculate final performance metrics
        self.calculate_performance_metrics()
        return self.metrics

    def calculate_performance_metrics(self):
        """Calculate advanced performance metrics."""
        if not self.metrics['trade_pnls']:
            return
        
        trade_pnls = np.array(self.metrics['trade_pnls'])
        total_trades = len(trade_pnls)
        
        # Calculate metrics
        self.metrics.update({
            'win_rate': (self.metrics['win_count'] / total_trades * 100) if total_trades > 0 else 0,
            'avg_trade_pnl': np.mean(trade_pnls),
            'std_trade_pnl': np.std(trade_pnls),
            'sharpe_ratio': (np.mean(trade_pnls) / np.std(trade_pnls) * np.sqrt(252)) if np.std(trade_pnls) > 0 else 0,
            'max_drawdown': self._calculate_max_drawdown(),
            'total_fees': sum(
                sum(fees.values()) 
                for exchange_fees in self.metrics['fees_paid'].values()
                for fees in [exchange_fees]
            )
        })

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from cumulative PnL history."""
        if not self.metrics['cumulative_pnls']:
            return 0.0
        
        cumulative = np.array(self.metrics['cumulative_pnls'])
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak
        return float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

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

    def print_results(self, symbol: Optional[str] = None):
        """Print backtest results for a specific symbol or overall."""
        if symbol:
            print(f"\n=== {symbol} Results ===")
            print(f"Trades: {self.metrics['trades_per_symbol'][symbol]}")
            print("\nTrades by Timeframe:")
            for tf, count in self.metrics['trades_per_timeframe'].items():
                print(f"{tf}: {count} trades, PnL: {self.metrics['pnl_per_timeframe'][tf]:.8f}")
        else:
            print("\n=== Overall Results ===")
            print(f"Total PnL: {self.metrics['total_pnl']:.8f}")
            print(f"Total Fees: {self.metrics['total_fees']:.8f}")
            print(f"Net PnL (after fees): {(self.metrics['total_pnl'] - self.metrics['total_fees']):.8f}")
            print(f"Win Rate: {self.metrics['win_rate']:.2f}%")
            print(f"Sharpe Ratio: {self.metrics['sharpe_ratio']:.2f}")
            print(f"Max Drawdown: {self.metrics['max_drawdown']:.2%}")
            print("\nFees by Exchange:")
            for exchange, fees in self.metrics['fees_paid'].items():
                print(f"{exchange}: Maker={fees['maker']:.8f}, Taker={fees['taker']:.8f}")
            print("\nTrades per Symbol:")
            for sym, count in self.metrics['trades_per_symbol'].items():
                print(f"{sym}: {count}")
            print("\nTrades by Timeframe:")
            for tf, count in self.metrics['trades_per_timeframe'].items():
                pnl = self.metrics['pnl_per_timeframe'][tf]
                print(f"{tf}: {count} trades, PnL: {pnl:.8f}")

    def run_all(self):
        """Run backtest for all configured symbols."""
        for symbol in SYMBOLS:
            logger.info(f"\nBacktesting {symbol}...")
            self.run_backtest(symbol)
            self.print_results(symbol)
        
        # Print overall results
        self.print_results()

if __name__ == "__main__":
    # Usage: python -m crypto_hft_tool.backtest
    backtester = Backtester()
    backtester.run_all() 