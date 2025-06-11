"""
Basic Risk Manager for the crypto HFT tool.
Handles position limits, stop losses, and basic risk controls.
"""
from typing import Dict, Optional
from datetime import datetime, timedelta

from .utils.logging_config import get_logger

logger = get_logger(__name__)


class RiskManager:
    """
    Basic risk management for trading operations.
    """
    
    def __init__(
        self,
        max_position_size: float = 0.1,
        max_daily_loss: float = 0.01,
        stop_loss_percentage: float = 0.02,
        position_timeout_minutes: int = 60
    ):
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.stop_loss_percentage = stop_loss_percentage
        self.position_timeout_minutes = position_timeout_minutes
        
        # Track current state
        self.current_positions: Dict[str, Dict] = {}
        self.daily_pnl = 0.0
        self.daily_loss_limit_reached = False
        self.entry_spreads: Dict[str, float] = {}
        self.last_reset = datetime.now().date()
        
    def can_trade(self, symbol: str, amount: float) -> bool:
        """
        Check if a trade is allowed based on risk parameters.
        
        Args:
            symbol: Trading symbol
            amount: Trade amount
            
        Returns:
            True if trade is allowed, False otherwise
        """
        # Check daily loss limit
        if self.daily_loss_limit_reached:
            logger.warning("Daily loss limit reached, blocking new trades")
            return False
            
        # Check position size limits
        current_position = self.current_positions.get(symbol, {}).get('size', 0.0)
        if abs(current_position + amount) > self.max_position_size:
            logger.warning(f"Position size limit exceeded for {symbol}")
            return False
            
        # Reset daily tracking if new day
        self._check_daily_reset()
        
        return True
        
    def register_trade(self, amount: float, pnl: float, entry_spread: float = None, direction: int = 1):
        """
        Register a completed trade for risk tracking.
        
        Args:
            amount: Trade amount
            pnl: Profit/loss from the trade
            entry_spread: Spread at entry (optional)
            direction: Trade direction (1 for long, -1 for short)
        """
        self.daily_pnl += pnl
        
        # Check if daily loss limit reached
        if self.daily_pnl <= -self.max_daily_loss:
            self.daily_loss_limit_reached = True
            logger.warning(f"Daily loss limit reached: {self.daily_pnl:.6f}")
            
        # Store entry spread for stop-loss monitoring
        if entry_spread is not None:
            trade_id = f"trade_{datetime.now().timestamp()}"
            self.entry_spreads[trade_id] = entry_spread
            
    def check_stop_loss(self, current_spread: float, entry_spread: float = None) -> bool:
        """
        Check if stop-loss should be triggered.
        
        Args:
            current_spread: Current market spread
            entry_spread: Original entry spread (optional)
            
        Returns:
            True if stop-loss should be triggered
        """
        if entry_spread is None:
            # Use the most recent entry spread if not provided
            if not self.entry_spreads:
                return False
            entry_spread = list(self.entry_spreads.values())[-1]
            
        # Calculate percentage change from entry
        if entry_spread != 0:
            spread_change = abs(current_spread - entry_spread) / abs(entry_spread)
            if spread_change > self.stop_loss_percentage:
                logger.warning(f"Stop-loss triggered: {spread_change:.4f} > {self.stop_loss_percentage:.4f}")
                return True
                
        return False
        
    def reset_entry_state(self):
        """Reset entry state after a stop-loss or position closure."""
        self.entry_spreads.clear()
        
    def update_position(self, symbol: str, amount: float, price: float):
        """
        Update position tracking.
        
        Args:
            symbol: Trading symbol
            amount: Position change amount
            price: Current price
        """
        if symbol not in self.current_positions:
            self.current_positions[symbol] = {
                'size': 0.0,
                'avg_price': 0.0,
                'timestamp': datetime.now()
            }
            
        position = self.current_positions[symbol]
        old_size = position['size']
        
        # Update position size
        position['size'] += amount
        
        # Update average price if increasing position
        if (old_size >= 0 and amount > 0) or (old_size <= 0 and amount < 0):
            total_value = old_size * position['avg_price'] + amount * price
            position['size'] = old_size + amount
            if position['size'] != 0:
                position['avg_price'] = total_value / position['size']
                
        position['timestamp'] = datetime.now()
        
    def get_position_info(self, symbol: str) -> Dict:
        """Get current position information for a symbol."""
        return self.current_positions.get(symbol, {
            'size': 0.0,
            'avg_price': 0.0,
            'timestamp': None
        })
        
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics."""
        return {
            'daily_pnl': self.daily_pnl,
            'daily_loss_limit_reached': self.daily_loss_limit_reached,
            'active_positions': len([p for p in self.current_positions.values() if p['size'] != 0]),
            'total_position_value': sum(
                abs(p['size'] * p['avg_price']) 
                for p in self.current_positions.values()
            )
        }
        
    def _check_daily_reset(self):
        """Check if we need to reset daily tracking."""
        current_date = datetime.now().date()
        if current_date > self.last_reset:
            self.daily_pnl = 0.0
            self.daily_loss_limit_reached = False
            self.last_reset = current_date
            logger.info("Daily risk metrics reset") 