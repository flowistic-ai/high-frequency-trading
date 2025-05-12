from .config import FEES
import logging

logger = logging.getLogger(__name__)

class TradeSimulator:
    """
    Simulates a round-trip arbitrage trade between two exchanges,
    accounting for maker/taker fees.
    """

    def __init__(self):
        # Track cumulative PnL
        self.total_pnl = 0.0
        self.trades = []

    def simulate_trade(
        self,
        symbol: str,
        buy_exchange: str,
        buy_price: float,
        sell_exchange: str,
        sell_price: float,
        amount: float,
    ) -> float:
        """
        Simulate buying `amount` of asset at `buy_price` on buy_exchange
        and selling the same `amount` at `sell_price` on sell_exchange.
        Deducts taker fee on buy and maker fee on sell.
        Returns PnL for this trade.
        """
        fees = FEES
        # Cost to buy
        cost = buy_price * amount
        buy_fee = cost * fees[buy_exchange]["taker"]

        # Proceeds from sell
        proceeds = sell_price * amount
        sell_fee = proceeds * fees[sell_exchange]["maker"]

        # Net PnL
        pnl = proceeds - sell_fee - (cost + buy_fee)
        self.total_pnl += pnl

        # Log trade
        trade = {
            "symbol": symbol,
            "buy_exchange": buy_exchange,
            "buy_price": buy_price,
            "sell_exchange": sell_exchange,
            "sell_price": sell_price,
            "amount": amount,
            "buy_fee": buy_fee,
            "sell_fee": sell_fee,
            "pnl": pnl,
            "cumulative_pnl": self.total_pnl,
        }
        self.trades.append(trade)
        logger.info(f"Simulated trade: {trade}")
        return pnl

    def reset(self):
        """Clear all simulated trades and PnL."""
        self.total_pnl = 0.0
        self.trades.clear()
