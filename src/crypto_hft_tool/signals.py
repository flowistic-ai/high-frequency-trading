from collections import deque
import numpy as np
import logging

logger = logging.getLogger(__name__)

class RollingZScore:
    """
    Maintains a fixed-size window of numeric values and computes
    the rolling Z-score for the most recent value.
    """
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.values = deque(maxlen=window_size)

    def add(self, value: float) -> float:
        """
        Add a new spread value, update the window, and return its Z-score.
        If there are fewer than 2 values, returns 0.0.
        """
        self.values.append(value)
        if len(self.values) < 2:
            return 0.0

        data = np.array(self.values, dtype=float)
        mean = data.mean()
        std = data.std(ddof=0)  # population std

        if std == 0:
            return 0.0

        z_score = (value - mean) / std
        logger.debug(
            f"RollingZScore | new={value:.6f}, mean={mean:.6f}, std={std:.6f}, z={z_score:.3f}"
        )
        return float(z_score)
