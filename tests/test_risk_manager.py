import pytest
from crypto_hft_tool.risk_manager import RiskManager
from crypto_hft_tool.config import MAX_NOTIONAL_PER_TRADE, MAX_TOTAL_NOTIONAL

def test_can_trade_within_limits():
    rm = RiskManager()
    sym = next(iter(MAX_NOTIONAL_PER_TRADE))
    amt = MAX_NOTIONAL_PER_TRADE[sym] * 0.5
    assert rm.can_trade(sym, amt)

def test_exceeds_per_trade():
    rm = RiskManager()
    sym = next(iter(MAX_NOTIONAL_PER_TRADE))
    amt = MAX_NOTIONAL_PER_TRADE[sym] * 2
    assert not rm.can_trade(sym, amt)

def test_exceeds_total_notional():
    rm = RiskManager()
    sym = next(iter(MAX_NOTIONAL_PER_TRADE))
    # First “use up” exposure
    rm.active_notional = MAX_TOTAL_NOTIONAL
    amt = 0.0001
    assert not rm.can_trade(sym, amt)

def test_drawdown_blocks_trades():
    rm = RiskManager()
    rm.cumulative_pnl = -abs(rm.cumulative_pnl) - 1.0  # below any MAX_DRAWDOWN
    sym = next(iter(MAX_NOTIONAL_PER_TRADE))
    assert not rm.can_trade(sym, 0.0001)

def test_stop_loss_trigger():
    from crypto_hft_tool.config import STOP_LOSS_SPREAD
    rm = RiskManager()
    assert rm.check_stop_loss(1.0, 1.0 + STOP_LOSS_SPREAD + 0.1)
    assert not rm.check_stop_loss(1.0, 1.0 + STOP_LOSS_SPREAD - 0.01)
