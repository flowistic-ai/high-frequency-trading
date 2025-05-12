from .config import (
    MAX_NOTIONAL_PER_TRADE,
    MAX_TOTAL_NOTIONAL,
    STOP_LOSS_SPREAD_AMOUNT,
    MAX_DRAWDOWN,
)
import logging

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Enforces risk rules: exposure caps, drawdown limits, and stop-loss based on spread movement.
    """

    def __init__(self):
        self.active_notional = 0.0
        self.cumulative_pnl = 0.0
        self.last_entry_spread: float | None = None
        self.last_trade_direction: int | None = None

    def can_trade(self, symbol: str, amount: float) -> bool:
        """Check notional exposure caps before executing a new trade."""
        max_trade = MAX_NOTIONAL_PER_TRADE.get(symbol, None)
        if max_trade is None:
            logger.warning(f"No MAX_NOTIONAL_PER_TRADE set for {symbol}; rejecting trade")
            return False
        if amount > max_trade:
            logger.info(f"Trade amount {amount} > max per-trade notional {max_trade}")
            return False
        if self.active_notional + amount > MAX_TOTAL_NOTIONAL:
            logger.info(
                f"Active notional {self.active_notional} + {amount} exceeds MAX_TOTAL_NOTIONAL {MAX_TOTAL_NOTIONAL}"
            )
            return False
        if self.cumulative_pnl <= MAX_DRAWDOWN:
            logger.warning(
                f"Cumulative PnL {self.cumulative_pnl:.6f} <= MAX_DRAWDOWN {MAX_DRAWDOWN}; halting new trades"
            )
            return False
        return True

    def register_trade(self, amount: float, pnl: float, entry_spread: float, direction: int):
        """
        Update exposure, PnL, and store entry conditions for stop-loss checks.
        Direction: 1 if expecting spread to decrease (Z>0 trade), -1 if expecting increase (Z<0 trade).
        """
        self.cumulative_pnl += pnl
        self.last_entry_spread = entry_spread
        self.last_trade_direction = direction
        logger.info(
            f"Trade registered. PnL: {pnl:.6f}, Cum. PnL: {self.cumulative_pnl:.6f}. "
            f"Entry Spread: {entry_spread:.4f}, Direction: {direction}"
        )
    
    def check_stop_loss(self, current_spread: float) -> bool:
        """
        Check if the current spread triggers a stop-loss based on the last entry.
        Returns True if stop-loss is hit, False otherwise.
        """
        if self.last_entry_spread is None or self.last_trade_direction is None:
            return False

        stop_loss_level = 0.0
        stop_loss_hit = False

        if self.last_trade_direction == 1:
            stop_loss_level = self.last_entry_spread + STOP_LOSS_SPREAD_AMOUNT
            if current_spread >= stop_loss_level:
                logger.warning(
                    f"STOP-LOSS HIT (Short Spread): Current Spread {current_spread:.4f} >= "
                    f"Entry {self.last_entry_spread:.4f} + Stop {STOP_LOSS_SPREAD_AMOUNT} = {stop_loss_level:.4f}"
                )
                stop_loss_hit = True
        
        elif self.last_trade_direction == -1:
            stop_loss_level = self.last_entry_spread - STOP_LOSS_SPREAD_AMOUNT
            if current_spread <= stop_loss_level:
                logger.warning(
                    f"STOP-LOSS HIT (Long Spread): Current Spread {current_spread:.4f} <= "
                    f"Entry {self.last_entry_spread:.4f} - Stop {STOP_LOSS_SPREAD_AMOUNT} = {stop_loss_level:.4f}"
                )
                stop_loss_hit = True
        
        if stop_loss_hit:
            self.reset_entry_state()
            
        return stop_loss_hit

    def reset_entry_state(self):
        """Clears the last trade entry details, e.g., after a stop-loss."""
        self.last_entry_spread = None
        self.last_trade_direction = None
        logger.info("Last trade entry state reset (e.g., due to stop-loss).")
