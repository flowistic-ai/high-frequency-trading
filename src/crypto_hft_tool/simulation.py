from typing import List, Dict, Any, Tuple
from datetime import datetime
from .config import FEES

from .utils.logging_config import get_logger

logger = get_logger(__name__)

class TradeSimulator:
    """
    Simulates trades and tracks their outcomes.
    """
    def __init__(self):
        self.trades = []
        self.total_pnl = 0.0
        self.total_fees_paid = 0.0
        self.positions = {}
        self.z_score_threshold = 1.2
        self.trade_amount = 0.001
        self.exit_z_threshold = 0.3

    def update_settings(self, z_score_threshold: float, trade_amount: float, exit_z_threshold: float):
        """Update simulator settings."""
        self.z_score_threshold = z_score_threshold
        self.trade_amount = trade_amount
        self.exit_z_threshold = exit_z_threshold
        logger.info(f"Updated simulator settings: z_score={z_score_threshold}, trade_amount={trade_amount}, exit_z={exit_z_threshold}")

    def simulate_arbitrage_trade(
        self,
        symbol: str,
        amount: float,
        buy_exchange: str,
        buy_price: float,
        sell_exchange: str,
        sell_price: float,
        buy_fee_rate: float,
        sell_fee_rate: float
    ) -> Tuple[float, float]:
        """
        Simulates a complete cross-exchange arbitrage trade.
        Returns (net_pnl, total_fees_for_this_arbitrage_trade)
        """
        buy_cost = amount * buy_price
        sell_revenue = amount * sell_price

        buy_fee = buy_cost * buy_fee_rate
        sell_fee = sell_revenue * sell_fee_rate
        total_fees_for_trade = buy_fee + sell_fee

        net_pnl = sell_revenue - buy_cost - total_fees_for_trade

        self.total_pnl += net_pnl
        self.total_fees_paid += total_fees_for_trade

        self.trades.append({
            "timestamp": pd.Timestamp.now(),
            "symbol": symbol,
            "buy_exchange": buy_exchange,
            "buy_price": buy_price,
            "sell_exchange": sell_exchange,
            "sell_price": sell_price,
            "amount": amount,
            "pnl": net_pnl,
            "fees": total_fees_for_trade,
            "side": "arbitrage"
        })
        logger.info(f"Arbitrage executed: {amount:.8f} {symbol} BUY@{buy_price:.2f} ({buy_exchange}), SELL@{sell_price:.2f} ({sell_exchange}), PnL: {net_pnl:.8f}, Fees: {total_fees_for_trade:.8f}")
        return net_pnl, total_fees_for_trade

    def simulate_trade(
        self,
        symbol: str,
        exchange: str,
        side: str,
        amount: float,
        entry_price: float,
        fee_rate: float = 0.001
    ) -> Tuple[float, float, float]:
        """
        Simulate a single leg of a trade (e.g., for a single-exchange strategy or if legs are managed separately).
        Returns (pnl_contribution, actual_trade_price, fee_cost)
        This method's PnL interpretation might need adjustment if it coexists with arbitrage PnL.
        For now, it primarily updates total_fees_paid and logs a leg.
        """
        logger.warning("simulate_trade (single leg) was called. Ensure this is intended if primarily doing arbitrage.")
        actual_trade_price = entry_price
        fee_cost = amount * entry_price * fee_rate
        self.total_fees_paid += fee_cost
        
        pnl_contribution = -fee_cost

        self.trades.append({
            "timestamp": pd.Timestamp.now(),
            "symbol": symbol,
            ("buy_exchange" if side.lower() == "buy" else "sell_exchange"): exchange,
            ("buy_price" if side.lower() == "buy" else "sell_price"): entry_price,
            "amount": amount,
            "pnl": pnl_contribution,
            "fees": fee_cost,
            "side": side,
            ("sell_exchange" if side.lower() == "buy" else "buy_exchange"): "N/A",
            ("sell_price" if side.lower() == "buy" else "buy_price"): 0.0,
        })

        return pnl_contribution, actual_trade_price, fee_cost

    def reset(self):
        """Clear all simulated trades and PnL."""
        self.total_pnl = 0.0
        self.total_fees_paid = 0.0
        self.trades.clear()
        self.positions = {}
