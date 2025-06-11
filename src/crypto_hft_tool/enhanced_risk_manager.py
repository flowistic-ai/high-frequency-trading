"""
Enhanced Risk Manager for the crypto HFT tool.
Provides advanced risk management with portfolio-level controls,
volatility adjustments, and correlation analysis.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque

from .utils.logging_config import get_logger

logger = get_logger(__name__)


class EnhancedRiskManager:
    """
    Advanced risk management with portfolio-level controls.
    """
    
    def __init__(
        self,
        base_position_sizes: Dict[str, float],
        max_position_values: Dict[str, float],
        drawdown_limits: Dict[str, float],
        volatility_lookback: int = 300,
        correlation_lookback: int = 900,
        risk_free_rate: float = 0.0
    ):
        self.base_position_sizes = base_position_sizes
        self.max_position_values = max_position_values
        self.drawdown_limits = drawdown_limits
        self.volatility_lookback = volatility_lookback
        self.correlation_lookback = correlation_lookback
        self.risk_free_rate = risk_free_rate
        
        # Portfolio tracking
        self.positions = {}
        self.pnl_history = deque(maxlen=10000)
        self.price_history = defaultdict(lambda: deque(maxlen=max(volatility_lookback, correlation_lookback)))
        self.return_history = defaultdict(lambda: deque(maxlen=max(volatility_lookback, correlation_lookback)))
        
        # Risk metrics
        self.portfolio_var = 0.0
        self.correlation_matrix = {}
        self.volatility_estimates = {}
        self.current_drawdown = 0.0
        self.peak_portfolio_value = 0.0
        
        # Dynamic position sizing
        self.dynamic_sizing_enabled = True
        self.volatility_scaling_factor = 0.5
        
    def update_market_data(self, symbol: str, price: float, timestamp: datetime):
        """
        Update market data for risk calculations.
        
        Args:
            symbol: Trading symbol
            price: Current price
            timestamp: Data timestamp
        """
        # Store price history
        self.price_history[symbol].append((timestamp, price))
        
        # Calculate returns if we have previous price
        if len(self.price_history[symbol]) > 1:
            prev_price = self.price_history[symbol][-2][1]
            if prev_price > 0:
                return_val = (price - prev_price) / prev_price
                self.return_history[symbol].append(return_val)
        
        # Update volatility estimates
        self._update_volatility_estimate(symbol)
        
        # Update correlation matrix periodically
        if len(self.return_history[symbol]) % 100 == 0:
            self._update_correlation_matrix()
    
    def _update_volatility_estimate(self, symbol: str):
        """Update volatility estimate for a symbol."""
        if len(self.return_history[symbol]) < 20:
            return
            
        returns = np.array(list(self.return_history[symbol]))
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        self.volatility_estimates[symbol] = volatility
        
    def _update_correlation_matrix(self):
        """Update correlation matrix between symbols."""
        symbols = [s for s in self.return_history.keys() if len(self.return_history[s]) > 50]
        
        if len(symbols) < 2:
            return
            
        # Build correlation matrix
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i <= j:
                    corr = self._calculate_correlation(symbol1, symbol2)
                    self.correlation_matrix[(symbol1, symbol2)] = corr
                    self.correlation_matrix[(symbol2, symbol1)] = corr
    
    def _calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate correlation between two symbols."""
        returns1 = np.array(list(self.return_history[symbol1]))
        returns2 = np.array(list(self.return_history[symbol2]))
        
        # Align lengths
        min_len = min(len(returns1), len(returns2))
        if min_len < 20:
            return 0.0
            
        returns1 = returns1[-min_len:]
        returns2 = returns2[-min_len:]
        
        correlation = np.corrcoef(returns1, returns2)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0
    
    def calculate_position_size(self, symbol: str, signal_strength: float, current_price: float) -> float:
        """
        Calculate optimal position size based on risk metrics.
        
        Args:
            symbol: Trading symbol
            signal_strength: Strength of the trading signal (0-1)
            current_price: Current market price
            
        Returns:
            Recommended position size
        """
        base_size = self.base_position_sizes.get(symbol, 0.001)
        
        if not self.dynamic_sizing_enabled:
            return base_size
            
        # Volatility adjustment
        volatility = self.volatility_estimates.get(symbol, 0.1)
        vol_adjustment = 1.0 / (1.0 + volatility * self.volatility_scaling_factor)
        
        # Signal strength adjustment
        signal_adjustment = signal_strength ** 0.5  # Square root scaling
        
        # Portfolio heat adjustment
        portfolio_heat = self._calculate_portfolio_heat()
        heat_adjustment = 1.0 / (1.0 + portfolio_heat)
        
        # Correlation adjustment
        correlation_adjustment = self._calculate_correlation_adjustment(symbol)
        
        adjusted_size = (
            base_size * 
            vol_adjustment * 
            signal_adjustment * 
            heat_adjustment * 
            correlation_adjustment
        )
        
        # Apply maximum position limits
        max_value = self.max_position_values.get(symbol, float('inf'))
        max_size_by_value = max_value / current_price if current_price > 0 else base_size
        
        return min(adjusted_size, max_size_by_value)
    
    def _calculate_portfolio_heat(self) -> float:
        """Calculate current portfolio heat (risk exposure)."""
        if not self.positions:
            return 0.0
            
        total_risk = sum(
            abs(pos.get('size', 0) * pos.get('price', 0)) 
            for pos in self.positions.values()
        )
        
        # Normalize by some base portfolio value
        base_portfolio_value = 10000  # Adjust based on your setup
        return total_risk / base_portfolio_value
    
    def _calculate_correlation_adjustment(self, symbol: str) -> float:
        """Calculate position size adjustment based on correlations."""
        if not self.positions or symbol not in self.correlation_matrix:
            return 1.0
            
        # Calculate portfolio correlation exposure
        total_correlation = 0.0
        active_positions = 0
        
        for other_symbol, position in self.positions.items():
            if other_symbol != symbol and position.get('size', 0) != 0:
                corr_key = (symbol, other_symbol)
                correlation = self.correlation_matrix.get(corr_key, 0.0)
                position_weight = abs(position.get('size', 0))
                total_correlation += abs(correlation) * position_weight
                active_positions += 1
        
        if active_positions == 0:
            return 1.0
            
        avg_correlation = total_correlation / active_positions
        return 1.0 / (1.0 + avg_correlation)
    
    def check_risk_limits(self, symbol: str, position_size: float, current_price: float) -> bool:
        """
        Check if a trade violates risk limits.
        
        Args:
            symbol: Trading symbol
            position_size: Proposed position size
            current_price: Current market price
            
        Returns:
            True if trade is allowed, False otherwise
        """
        # Check position value limits
        position_value = abs(position_size * current_price)
        max_value = self.max_position_values.get(symbol, float('inf'))
        
        if position_value > max_value:
            logger.warning(f"Position value {position_value} exceeds limit {max_value} for {symbol}")
            return False
        
        # Check drawdown limits
        drawdown_limit = self.drawdown_limits.get(symbol, 0.1)
        if self.current_drawdown > drawdown_limit:
            logger.warning(f"Current drawdown {self.current_drawdown} exceeds limit {drawdown_limit}")
            return False
        
        # Check portfolio VaR
        if self._would_exceed_var_limit(symbol, position_size, current_price):
            logger.warning("Trade would exceed portfolio VaR limit")
            return False
            
        return True
    
    def _would_exceed_var_limit(self, symbol: str, position_size: float, current_price: float) -> bool:
        """Check if adding position would exceed VaR limits."""
        # Simplified VaR check - in production, use more sophisticated models
        portfolio_value = sum(
            abs(pos.get('size', 0) * pos.get('price', 0)) 
            for pos in self.positions.values()
        )
        
        new_position_value = abs(position_size * current_price)
        total_value = portfolio_value + new_position_value
        
        # Assume 1% daily VaR limit
        var_limit = total_value * 0.01
        
        return self.portfolio_var > var_limit
    
    def update_position(self, symbol: str, size: float, price: float, pnl: float = 0.0):
        """
        Update position tracking.
        
        Args:
            symbol: Trading symbol
            size: Position size change
            price: Trade price
            pnl: Realized PnL from the trade
        """
        if symbol not in self.positions:
            self.positions[symbol] = {'size': 0.0, 'avg_price': 0.0, 'unrealized_pnl': 0.0}
        
        position = self.positions[symbol]
        old_size = position['size']
        
        # Update position
        position['size'] += size
        
        # Update average price
        if (old_size >= 0 and size > 0) or (old_size <= 0 and size < 0):
            if position['size'] != 0:
                total_cost = old_size * position['avg_price'] + size * price
                position['avg_price'] = total_cost / position['size']
        
        position['price'] = price
        position['timestamp'] = datetime.now()
        
        # Track PnL
        if pnl != 0:
            self.pnl_history.append((datetime.now(), pnl))
            self._update_drawdown_metrics()
    
    def _update_drawdown_metrics(self):
        """Update portfolio drawdown metrics."""
        if len(self.pnl_history) < 2:
            return
            
        # Calculate cumulative PnL
        cumulative_pnl = sum(pnl for _, pnl in self.pnl_history)
        
        # Update peak value
        if cumulative_pnl > self.peak_portfolio_value:
            self.peak_portfolio_value = cumulative_pnl
            
        # Calculate current drawdown
        self.current_drawdown = (self.peak_portfolio_value - cumulative_pnl) / abs(self.peak_portfolio_value) if self.peak_portfolio_value != 0 else 0.0
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics."""
        return {
            'portfolio_var': self.portfolio_var,
            'current_drawdown': self.current_drawdown,
            'peak_portfolio_value': self.peak_portfolio_value,
            'active_positions': len([p for p in self.positions.values() if p['size'] != 0]),
            'volatility_estimates': self.volatility_estimates.copy(),
            'portfolio_heat': self._calculate_portfolio_heat(),
            'correlation_matrix_size': len(self.correlation_matrix)
        } 