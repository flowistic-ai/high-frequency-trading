from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from .utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class VolumeTier:
    maker_fee: float
    taker_fee: float
    min_volume: float
    currency: str  # 'BTC' or 'USD'

class FeeManager:
    """
    Manages exchange fees, volume tiers, and fee calculations for trades
    """
    def __init__(self):
        # Default fee structure
        self.exchange_fees = {
            'binance': {
                'default': {'maker': 0.0010, 'taker': 0.0010},  # 0.10%
                'volume_tiers': [
                    VolumeTier(0.0009, 0.0009, 50.0, 'BTC'),   # 50 BTC volume
                    VolumeTier(0.0008, 0.0008, 100.0, 'BTC'),  # 100 BTC volume
                    VolumeTier(0.0007, 0.0007, 500.0, 'BTC'),  # 500 BTC volume
                ]
            },
            'kraken': {
                'default': {'maker': 0.0016, 'taker': 0.0026},  # 0.16%/0.26%
                'volume_tiers': [
                    VolumeTier(0.0014, 0.0024, 50000.0, 'USD'),  # 50K USD volume
                    VolumeTier(0.0012, 0.0022, 100000.0, 'USD'), # 100K USD volume
                    VolumeTier(0.0010, 0.0020, 250000.0, 'USD'), # 250K USD volume
                ]
            }
        }
        
        # Track 30-day rolling volume
        self.volume_history = {
            'binance': [],
            'kraken': []
        }
        
    def add_volume(self, exchange: str, amount: float, price: float, timestamp: Optional[datetime] = None):
        """
        Record trading volume for fee tier calculation
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        volume_usd = amount * price
        self.volume_history[exchange].append((timestamp, volume_usd))
        
        # Clean up old volume data (older than 30 days)
        cutoff = timestamp - timedelta(days=30)
        self.volume_history[exchange] = [
            (ts, vol) for ts, vol in self.volume_history[exchange]
            if ts > cutoff
        ]
        
    def get_30d_volume(self, exchange: str, in_btc: bool = False) -> float:
        """
        Calculate 30-day trading volume for an exchange
        """
        total_volume = sum(vol for _, vol in self.volume_history[exchange])
        if in_btc and exchange == 'binance':
            # Convert USD volume to BTC (using approximate price)
            # In production, this should use actual BTC price
            total_volume = total_volume / 30000  # Approximate BTC price
        return total_volume
        
    def get_fees(self, exchange: str, is_maker: bool = False) -> float:
        """
        Get current fees based on 30-day volume
        """
        volume = self.get_30d_volume(exchange, in_btc=(exchange == 'binance'))
        fee_type = 'maker' if is_maker else 'taker'
        
        # Get default fee
        current_fee = self.exchange_fees[exchange]['default'][fee_type]
        
        # Check volume tiers
        for tier in self.exchange_fees[exchange]['volume_tiers']:
            if volume >= tier.min_volume:
                current_fee = tier.maker_fee if is_maker else tier.taker_fee
            else:
                break
                
        return current_fee
        
    def estimate_fees(self, exchange: str, amount: float, price: float, is_maker: bool = False) -> float:
        """
        Estimate fees for a potential trade
        """
        fee_rate = self.get_fees(exchange, is_maker)
        trade_value = amount * price
        return trade_value * fee_rate
        
    def calculate_effective_price(self, price: float, exchange: str, is_buy: bool, is_maker: bool = False) -> float:
        """
        Calculate effective price after fees
        """
        fee_rate = self.get_fees(exchange, is_maker)
        logger.debug(f"Fee rate for {exchange} ({'maker' if is_maker else 'taker'}): {fee_rate:.6f}")
        
        if is_buy:
            effective_price = price * (1 + fee_rate)  # Higher effective price when buying
            logger.debug(f"Buy price adjustment: {price:.2f} -> {effective_price:.2f}")
        else:
            effective_price = price * (1 - fee_rate)  # Lower effective price when selling
            logger.debug(f"Sell price adjustment: {price:.2f} -> {effective_price:.2f}")
            
        return effective_price 