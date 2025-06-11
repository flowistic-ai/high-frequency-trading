import numpy as np
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from .signals import RollingZScore
from .utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class SignalMetrics:
    """Holds signal metrics for a given timeframe"""
    zscore: float
    volume_weighted_zscore: float
    momentum_score: float
    correlation_filter: float
    volatility: float
    threshold: float
    signal_strength: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

class EnhancedSignalProcessor:
    """
    Enhanced signal processor that combines multiple indicators
    for more robust trading signals.
    """
    def __init__(
        self,
        symbol: str,
        volatility_window: int = 100,
        correlation_window: int = 50,
        momentum_window: int = 20,
        signal_threshold: float = 1.0,
        vol_impact: float = 0.5
    ):
        self.symbol = symbol
        self.volatility_window = volatility_window
        self.correlation_window = correlation_window
        self.momentum_window = momentum_window
        self.base_signal_threshold = signal_threshold
        self.vol_impact = vol_impact
        
        # Historical data storage
        self.spreads = []
        self.volumes = []
        self.timestamps = []
        self.zscores = []
        self.thresholds = []
        
        # Market state tracking
        self.volatility = 0.0
        self.momentum = 0.0
        self.last_signal = "HOLD"
        self.signal_duration = 0
        
    def _calculate_adaptive_threshold(self, current_volatility: float, current_volume: float) -> float:
        """Calculate adaptive threshold based on market conditions"""
        try:
            # Base threshold adjustment based on volatility
            vol_adjustment = 1.0 + (current_volatility * self.vol_impact)
            
            # Volume impact - lower threshold during high volume periods
            avg_volume = np.mean(self.volumes[-20:]) if len(self.volumes) >= 20 else current_volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            vol_factor = 1.0 / (1.0 + np.log1p(volume_ratio))
            
            # Time of day adjustment (markets are typically more volatile during certain hours)
            hour = datetime.now().hour
            time_factor = 1.0
            if 8 <= hour <= 16:  # During main trading hours
                time_factor = 0.9  # Lower threshold during active hours
            elif 0 <= hour <= 4:  # During typically low liquidity hours
                time_factor = 1.2  # Higher threshold during low liquidity
            
            # Momentum adjustment
            momentum_impact = abs(self.momentum) * 0.1
            
            # Combine all factors
            adaptive_threshold = (
                self.base_signal_threshold *
                vol_adjustment *
                vol_factor *
                time_factor *
                (1.0 + momentum_impact)
            )
            
            # Ensure threshold stays within reasonable bounds
            return np.clip(adaptive_threshold, 0.5, 5.0)
            
        except Exception as e:
            logger.error(f"Error calculating adaptive threshold: {e}")
            return self.base_signal_threshold
            
    def update(self, spread: float, volume: float, timestamp: datetime) -> Dict[int, SignalMetrics]:
        try:
            # Store historical data
            self.spreads.append(spread)
            self.volumes.append(volume)
            self.timestamps.append(timestamp)
            
            # Keep only required history
            max_window = max(self.volatility_window, self.correlation_window, self.momentum_window)
            if len(self.spreads) > max_window:
                self.spreads = self.spreads[-max_window:]
                self.volumes = self.volumes[-max_window:]
                self.timestamps = self.timestamps[-max_window:]
            
            # Return default values if not enough data
            if len(self.spreads) < 2:
                return {
                    self.volatility_window: SignalMetrics(
                        zscore=0.0,
                        volume_weighted_zscore=0.0,
                        momentum_score=0.0,
                        correlation_filter=0.0,
                        volatility=0.0,
                        threshold=self.base_signal_threshold,
                        signal_strength=0.0
                    )
                }
                
            # Calculate returns and volatility
            returns = np.diff(self.spreads) / self.spreads[:-1]
            self.volatility = np.std(returns) * np.sqrt(252)  # Annualized
            
            # Calculate momentum
            if len(returns) >= self.momentum_window:
                recent_returns = returns[-self.momentum_window:]
                self.momentum = np.sum(recent_returns)
            
            # Calculate volume-weighted z-score
            mean_spread = np.mean(self.spreads)
            std_spread = np.std(self.spreads)
            if std_spread > 0:
                raw_zscore = (spread - mean_spread) / std_spread
                volume_weight = volume / np.mean(self.volumes)
                volume_weighted_zscore = raw_zscore * volume_weight
            else:
                raw_zscore = 0.0
                volume_weighted_zscore = 0.0
            
            # Calculate adaptive threshold
            threshold = self._calculate_adaptive_threshold(self.volatility, volume)
            
            # Calculate signal strength
            signal_strength = abs(volume_weighted_zscore)
            
            # Store for historical reference
            self.zscores.append(raw_zscore)
            self.thresholds.append(threshold)
            
            return {
                self.volatility_window: SignalMetrics(
                    zscore=raw_zscore,
                    volume_weighted_zscore=volume_weighted_zscore,
                    momentum_score=self.momentum,
                    correlation_filter=0.0,  # Not implemented in this version
                    volatility=self.volatility,
                    threshold=threshold,
                    signal_strength=signal_strength
                )
            }
            
        except Exception as e:
            logger.error(f"Error updating signal processor: {e}")
            return {} 