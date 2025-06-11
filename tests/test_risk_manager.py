import pytest
from crypto_hft_tool.risk_manager import RiskManager

def test_can_trade_within_limits():
    """Test that trades within position limits are allowed"""
    rm = RiskManager(max_position_size=0.1)
    assert rm.can_trade("BTC/USDT", 0.05)

def test_exceeds_position_limit():
    """Test that trades exceeding position limits are blocked"""
    rm = RiskManager(max_position_size=0.1)
    # Add a position first
    rm.update_position("BTC/USDT", 0.08, 30000.0)
    # Try to add more that would exceed limit
    assert not rm.can_trade("BTC/USDT", 0.05)

def test_daily_loss_limit():
    """Test that trades are blocked when daily loss limit is reached"""
    rm = RiskManager(max_daily_loss=0.01)
    # Register a large loss
    rm.register_trade(0.001, -0.02)  # Loss exceeds daily limit
    assert not rm.can_trade("BTC/USDT", 0.001)

def test_stop_loss_trigger():
    """Test stop-loss triggering"""
    rm = RiskManager(stop_loss_percentage=0.02)
    entry_spread = 100.0
    current_spread = 105.0  # 5% increase, above 2% threshold
    assert rm.check_stop_loss(current_spread, entry_spread)
    
    # Test within threshold
    current_spread = 101.0  # 1% increase, below 2% threshold
    assert not rm.check_stop_loss(current_spread, entry_spread)

def test_position_tracking():
    """Test position tracking functionality"""
    rm = RiskManager()
    rm.update_position("BTC/USDT", 0.05, 30000.0)
    
    position = rm.get_position_info("BTC/USDT")
    assert position['size'] == 0.05
    assert position['avg_price'] == 30000.0

def test_risk_metrics():
    """Test risk metrics calculation"""
    rm = RiskManager()
    rm.register_trade(0.001, 0.01)  # Profitable trade
    
    metrics = rm.get_risk_metrics()
    assert metrics['daily_pnl'] == 0.01
    assert not metrics['daily_loss_limit_reached']

def test_daily_reset():
    """Test daily metrics reset"""
    rm = RiskManager(max_daily_loss=0.01)
    rm.register_trade(0.001, -0.02)  # Large loss
    assert rm.daily_loss_limit_reached
    
    # Manually trigger reset (in real usage this happens automatically at midnight)
    rm._check_daily_reset()
    # Note: In actual test, we'd need to mock datetime to test automatic reset
