import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from crypto_hft_tool.backtest import Backtester
from crypto_hft_tool.config import ZSCORE_SETTINGS, TRADE_SETTINGS

# Import centralized logging setup
from crypto_hft_tool.utils.logging_config import setup_logging

# Configure logging for tests
setup_logging(level='DEBUG')

def create_sample_data(symbol: str = "BTC/USDT", rows: int = 1000):
    """Create synthetic market data for testing"""
    base_price = 30000.0
    timestamps = [(datetime.utcnow() + timedelta(seconds=i)).timestamp() for i in range(rows)]
    
    # Generate price series with some randomness and trend
    price_changes = np.random.normal(0, 20, rows).cumsum()
    binance_prices = base_price + price_changes
    kraken_prices = binance_prices + np.random.normal(0, 5, rows)  # Add some exchange difference
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'binance_bid': binance_prices - 0.5,
        'binance_ask': binance_prices + 0.5,
        'kraken_bid': kraken_prices - 0.5,
        'kraken_ask': kraken_prices + 0.5
    })
    return df

def test_backtester_initialization():
    """Test backtester initialization with new components"""
    backtester = Backtester()
    
    # Check Z-score trackers initialization
    assert len(backtester.ztrackers) == len(backtester.metrics['trades_per_symbol'])
    assert all(str(tf) in backtester.metrics['trades_per_timeframe'] 
              for tf in ZSCORE_SETTINGS['windows'])
    
    # Check fee manager initialization
    assert hasattr(backtester, 'fee_manager')
    assert 'binance' in backtester.metrics['fees_paid']
    assert 'kraken' in backtester.metrics['fees_paid']

def test_trade_conditions():
    """Test trade condition checking"""
    backtester = Backtester()
    
    # Test case: Valid trade conditions
    z_scores = {
        'ultra_short': 2.5,  # Increased to ensure it's above threshold
        'short': 2.2,
        'medium': 1.8,
        'long': 1.5
    }
    
    # Create prices with sufficient spread for minimum profit
    base_price = 30000.0
    spread_pct = 0.005  # 0.5% spread (increased to ensure profitability after fees)
    spread_amount = base_price * spread_pct
    
    # Create a profitable arbitrage opportunity:
    # Kraken prices are significantly lower than Binance
    prices = {
        'binance': {
            'bid': base_price + spread_amount/2,    # Higher prices on Binance
            'ask': base_price + spread_amount
        },
        'kraken': {
            'bid': base_price - spread_amount/2,    # Lower prices on Kraken
            'ask': base_price - spread_amount/4
        }
    }
    
    # Calculate actual spread between exchanges
    spread = prices['binance']['ask'] - prices['kraken']['bid']
    
    # Print debug information
    print(f"\nTest Configuration:")
    print(f"Base Price: {base_price}")
    print(f"Spread Amount: {spread_amount}")
    print(f"Binance: bid={prices['binance']['bid']}, ask={prices['binance']['ask']}")
    print(f"Kraken: bid={prices['kraken']['bid']}, ask={prices['kraken']['ask']}")
    print(f"Inter-exchange Spread: {spread}")
    print(f"Spread Ratio: {abs(spread)/base_price}")
    print(f"Min Required Spread Ratio: {TRADE_SETTINGS['thresholds']['min_spread_ratio']}")
    
    trade_params = backtester._check_trade_conditions(
        symbol="BTC/USDT",
        z_scores=z_scores,
        spread=spread,
        timestamp=datetime.utcnow(),
        prices=prices
    )
    
    assert trade_params is not None, "Trade conditions should be met"
    assert trade_params['timeframe'] == 'ultra_short'  # Should pick strongest signal
    assert trade_params['direction'] in [1, -1]
    assert trade_params['profit'] > 0, "Trade should be profitable after fees"
    
    # Test case: Invalid spread ratio
    prices = {
        'binance': {'bid': 30000.0, 'ask': 30300.0},  # 1% spread (too high)
        'kraken': {'bid': 29999.0, 'ask': 30000.0}
    }
    
    trade_params = backtester._check_trade_conditions(
        symbol="BTC/USDT",
        z_scores=z_scores,
        spread=301.0,
        timestamp=datetime.utcnow(),
        prices=prices
    )
    
    assert trade_params is None, "Trade should be rejected due to high spread"

def test_fee_calculation():
    """Test fee calculation and tracking"""
    backtester = Backtester()
    
    # Execute a trade
    trade_params = {
        'timeframe': 'ultra_short',
        'z_score': 2.0,
        'direction': 1,
        'profit': 1.0
    }
    prices = {
        'binance': {'bid': 30000.0, 'ask': 30001.0},
        'kraken': {'bid': 29999.0, 'ask': 30000.0}
    }
    
    pnl = backtester._execute_trade(
        symbol="BTC/USDT",
        trade_params=trade_params,
        prices=prices,
        timestamp=datetime.utcnow()
    )
    
    # Check fee tracking
    assert backtester.metrics['fees_paid']['binance']['taker'] > 0
    assert backtester.metrics['fees_paid']['kraken']['taker'] > 0
    assert backtester.metrics['total_pnl'] == pnl

def test_performance_metrics():
    """Test performance metric calculations"""
    backtester = Backtester()
    
    # Add some synthetic trades
    pnls = [0.1, -0.05, 0.15, -0.02, 0.08]
    for pnl in pnls:
        backtester.metrics['trade_pnls'].append(pnl)
        backtester.metrics['total_pnl'] += pnl
        backtester.metrics['cumulative_pnls'].append(backtester.metrics['total_pnl'])
        if pnl > 0:
            backtester.metrics['win_count'] += 1
        else:
            backtester.metrics['loss_count'] += 1
    
    backtester.calculate_performance_metrics()
    
    assert backtester.metrics['win_rate'] == 60.0  # 3 wins out of 5 trades
    assert abs(backtester.metrics['avg_trade_pnl'] - np.mean(pnls)) < 1e-10
    assert backtester.metrics['sharpe_ratio'] > 0  # Should be positive given our sample

def test_full_backtest():
    """Test full backtest execution"""
    backtester = Backtester()
    
    # Create sample data with more volatile price movements
    rows = 1000
    base_price = 30000.0
    timestamps = [(datetime.utcnow() + timedelta(seconds=i)).timestamp() for i in range(rows)]
    
    # Generate more volatile price series
    volatility = 100.0  # Increased volatility for more trading opportunities
    price_changes = np.random.normal(0, volatility, rows).cumsum()
    binance_prices = base_price + price_changes
    
    # Add larger exchange differences
    exchange_diff = np.random.normal(volatility * 0.2, volatility * 0.1, rows)  # Significant exchange differences
    kraken_prices = binance_prices + exchange_diff
    
    # Create DataFrame with wider spreads for profitable opportunities
    spread = base_price * 0.005  # 0.5% spread
    df = pd.DataFrame({
        'timestamp': timestamps,
        'binance_bid': binance_prices + spread/2,     # Higher prices on Binance
        'binance_ask': binance_prices + spread,
        'kraken_bid': kraken_prices - spread/2,       # Lower prices on Kraken
        'kraken_ask': kraken_prices - spread/4
    })
    
    # Save test data
    df.to_csv("data/processed/BTC_USDT.csv", index=False)
    
    # Run backtest
    metrics = backtester.run_backtest("BTC/USDT")
    
    print("\nBacktest Results:")
    print(f"Total PnL: {metrics['total_pnl']:.8f}")
    print(f"Total Fees: {metrics['total_fees']:.8f}")
    print(f"Net PnL: {metrics['total_pnl'] - metrics['total_fees']:.8f}")
    print(f"Total Trades: {len(metrics['trade_pnls'])}")
    print("\nTrades by Timeframe:")
    for tf, count in metrics['trades_per_timeframe'].items():
        print(f"{tf}: {count} trades, PnL: {metrics['pnl_per_timeframe'][tf]:.8f}")
    
    assert metrics['total_pnl'] != 0, "Should have executed some profitable trades"
    assert metrics['total_fees'] > 0, "Should have incurred some fees"
    assert len(metrics['trade_pnls']) > 0, "Should have executed some trades"
    assert metrics['total_pnl'] > metrics['total_fees'], "Should be profitable after fees"
    
    # Check timeframe tracking
    assert sum(metrics['trades_per_timeframe'].values()) == len(metrics['trade_pnls'])
    assert all(str(tf) in metrics['pnl_per_timeframe'] for tf in ZSCORE_SETTINGS['windows']) 