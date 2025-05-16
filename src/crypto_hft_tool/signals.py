from collections import deque
import numpy as np
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class TimeWindowData:
    values: deque
    timestamps: deque
    last_volatility: float = 0.0
    last_mean: float = 0.0
    last_std: float = 0.0

class RollingZScore:
    """
    Calculates z-scores on rolling windows of data.
    """
    def __init__(self, windows: List[int]):
        """
        Initialize with window sizes.
        windows: List[int] - e.g., [30, 60, 120]
        """
        self.windows = {str(w): w for w in windows}
        self.data = {
            name: deque(maxlen=size) 
            for name, size in self.windows.items()
        }
        self.last_zscore = {
            name: None for name in self.windows.keys()
        }

    def update(self, value: float) -> Dict[str, Optional[float]]:
        """
        Add a new value and return z-scores for all windows.
        """
        for window_name in self.windows:
            self.data[window_name].append(value)
            
            if len(self.data[window_name]) >= 2:  # Need at least 2 points for std
                values = np.array(self.data[window_name])
                mean = np.mean(values)
                std = np.std(values, ddof=1)  # ddof=1 for sample standard deviation
                
                if std > 0:  # Avoid division by zero
                    self.last_zscore[window_name] = (value - mean) / std
                else:
                    self.last_zscore[window_name] = 0.0
            else:
                self.last_zscore[window_name] = 0.0
                
        return self.last_zscore

    def get_last_zscores(self) -> Dict[str, Optional[float]]:
        """Get the most recently calculated z-scores without updating."""
        return self.last_zscore.copy()

    def reset(self):
        """Clear all data and reset z-scores."""
        for window_name in self.windows:
            self.data[window_name].clear()
            self.last_zscore[window_name] = None

    def _calculate_volatility_adjustment(self, timeframe: str) -> float:
        """
        Calculate volatility adjustment factor based on recent vs historical volatility
        """
        if not self.vol_adjustment:
            return 1.0
            
        window_data = self.data[timeframe]
        if len(window_data) < 30:  # Need minimum data points
            return 1.0
            
        recent_vol = np.std(list(window_data)[-30:], ddof=0)
        full_vol = self.last_volatility
        
        if full_vol == 0:
            return 1.0
            
        vol_ratio = recent_vol / full_vol
        # Bound the adjustment factor
        return max(0.5, min(2.0, vol_ratio))
        
    def _update_timeframe(self, timeframe: str, value: float, timestamp: datetime) -> Optional[float]:
        """
        Update statistics for a specific timeframe and return its Z-score
        """
        window_data = self.data[timeframe]
        
        # Remove old values based on timestamp
        window_size = self.windows[timeframe]
        cutoff_time = timestamp - timedelta(seconds=window_size)
        
        while window_data and window_data[0] < cutoff_time:
            window_data.popleft()
            
        # Add new value
        window_data.append(value)
        
        if len(window_data) < 2:
            return None
            
        # Calculate statistics
        data_array = np.array(window_data)
        mean = data_array.mean()
        std = data_array.std(ddof=0)
        
        if std == 0:
            return 0.0
            
        # Calculate volatility-adjusted z-score
        vol_adj = self._calculate_volatility_adjustment(timeframe)
        z_score = (value - mean) / (std * vol_adj)
        
        return float(z_score)
        
    def add(self, value: float, timestamp: Optional[datetime] = None) -> Dict[str, float]:
        """
        Add a new value and return Z-scores for all timeframes
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        z_scores = {}
        for timeframe in self.windows.keys():
            z_score = self._update_timeframe(timeframe, value, timestamp)
            if z_score is not None:
                z_scores[timeframe] = z_score
                
        # Log detailed information for debugging
        logger.debug(
            f"Z-scores: {', '.join(f'{tf}={z:.3f}' for tf, z in z_scores.items())}, "
            f"Value={value:.6f}, Timestamp={timestamp}"
        )
        
        return z_scores
        
    def get_statistics(self, timeframe: str) -> Dict[str, float]:
        """
        Get current statistics for a specific timeframe
        """
        window_data = self.data[timeframe]
        return {
            'mean': np.mean(window_data),
            'std': np.std(window_data, ddof=0),
            'volatility': self.last_volatility,
            'sample_size': len(window_data)
        }
