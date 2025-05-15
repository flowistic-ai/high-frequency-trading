import asyncio
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
import numpy as np

from .fee_manager import FeeManager

logger = logging.getLogger(__name__)

class ExecutionManager:
    def __init__(
        self,
        fee_manager: FeeManager,
        min_liquidity_ratio: float = 0.3,
        max_price_impact: float = 0.0001,  # 0.01%
        iceberg_threshold: float = 1.0,  # BTC
        min_fill_ratio: float = 0.95
    ):
        self.fee_manager = fee_manager
        self.min_liquidity_ratio = min_liquidity_ratio
        self.max_price_impact = max_price_impact
        self.iceberg_threshold = iceberg_threshold
        self.min_fill_ratio = min_fill_ratio
        
        # Execution metrics
        self.metrics = {
            'slippage': np.array([], dtype=np.float64),
            'fill_ratios': np.array([], dtype=np.float64),
            'execution_times': np.array([], dtype=np.float64),
            'price_impact': np.array([], dtype=np.float64)
        }
        
    def _calculate_liquidity_score(
        self,
        orderbook: Dict[str, Dict[Decimal, Decimal]],
        side: str,
        amount: float
    ) -> float:
        """Calculate liquidity score for an exchange"""
        try:
            book_side = orderbook['bids'] if side == 'sell' else orderbook['asks']
            total_liquidity = sum(float(amt) for amt in book_side.values())
            return min(1.0, total_liquidity / amount)
        except Exception as e:
            logger.error(f"Error calculating liquidity score: {e}")
            return 0.0
            
    def _estimate_price_impact(
        self,
        orderbook: Dict[str, Dict[Decimal, Decimal]],
        side: str,
        amount: float
    ) -> Tuple[float, float]:
        """Estimate price impact and average execution price"""
        try:
            book_side = orderbook['bids'] if side == 'sell' else orderbook['asks']
            prices = sorted(book_side.keys(), reverse=(side == 'sell'))
            
            remaining = amount
            total_cost = 0.0
            levels_used = 0
            
            for price in prices:
                available = float(book_side[price])
                taken = min(remaining, available)
                total_cost += taken * float(price)
                remaining -= taken
                levels_used += 1
                
                if remaining <= 0:
                    break
                    
            if remaining > 0:
                return float('inf'), 0.0
                
            avg_price = total_cost / amount
            reference_price = float(prices[0])  # Best bid/ask
            impact = abs(avg_price - reference_price) / reference_price
            
            return impact, avg_price
            
        except Exception as e:
            logger.error(f"Error estimating price impact: {e}")
            return float('inf'), 0.0
            
    def _should_use_iceberg(
        self,
        amount: float,
        orderbook: Dict[str, Dict[Decimal, Decimal]]
    ) -> Tuple[bool, Optional[float]]:
        """Determine if iceberg order should be used"""
        if amount < self.iceberg_threshold:
            return False, None
            
        # Calculate optimal chunk size based on orderbook depth
        total_depth = sum(
            float(amt) for amt in orderbook['bids'].values()
        ) + sum(
            float(amt) for amt in orderbook['asks'].values()
        )
        
        chunk_size = min(
            amount * 0.2,  # 20% of total order
            total_depth * 0.1  # 10% of orderbook depth
        )
        
        return True, max(chunk_size, 0.1)  # Minimum chunk size 0.1 BTC
        
    async def execute_order(
        self,
        exchange: str,
        exchange_client: object,
        symbol: str,
        side: str,
        amount: float,
        orderbook: Dict[str, Dict[Decimal, Decimal]],
        max_retries: int = 3
    ) -> Optional[Dict]:
        """Execute order with smart routing and anti-gaming logic"""
        try:
            start_time = datetime.now()
            
            # Check liquidity
            liquidity_score = self._calculate_liquidity_score(
                orderbook, side, amount
            )
            if liquidity_score < self.min_liquidity_ratio:
                logger.warning(
                    f"Insufficient liquidity on {exchange} for {symbol} "
                    f"({liquidity_score:.2f} < {self.min_liquidity_ratio})"
                )
                return None
                
            # Estimate price impact
            impact, avg_price = self._estimate_price_impact(
                orderbook, side, amount
            )
            if impact > self.max_price_impact:
                logger.warning(
                    f"Excessive price impact on {exchange} for {symbol} "
                    f"({impact:.4%} > {self.max_price_impact:.4%})"
                )
                return None
                
            # Check if iceberg order needed
            use_iceberg, chunk_size = self._should_use_iceberg(amount, orderbook)
            
            if use_iceberg:
                logger.info(
                    f"Using iceberg order for {symbol} on {exchange} "
                    f"(chunk size: {chunk_size:.3f})"
                )
                order = await self._execute_iceberg_order(
                    exchange_client,
                    symbol,
                    side,
                    amount,
                    chunk_size,
                    avg_price,
                    max_retries
                )
            else:
                order = await self._execute_single_order(
                    exchange_client,
                    symbol,
                    side,
                    amount,
                    avg_price,
                    max_retries
                )
                
            if not order:
                return None
                
            # Calculate execution metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            fill_ratio = float(order['filled']) / float(order['amount'])
            executed_price = float(order['average'])
            slippage = abs(executed_price - avg_price) / avg_price
            
            # Update metrics
            self.metrics['slippage'] = np.append(
                self.metrics['slippage'], slippage
            )
            self.metrics['fill_ratios'] = np.append(
                self.metrics['fill_ratios'], fill_ratio
            )
            self.metrics['execution_times'] = np.append(
                self.metrics['execution_times'], execution_time
            )
            self.metrics['price_impact'] = np.append(
                self.metrics['price_impact'], impact
            )
            
            # Trim metrics arrays
            if len(self.metrics['slippage']) > 1000:
                for key in self.metrics:
                    self.metrics[key] = self.metrics[key][-1000:]
                    
            return order
            
        except Exception as e:
            logger.error(f"Error executing order on {exchange}: {e}")
            return None
            
    async def _execute_single_order(
        self,
        exchange_client: object,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        max_retries: int
    ) -> Optional[Dict]:
        """Execute a single limit order"""
        retries = 0
        while retries < max_retries:
            try:
                order = await exchange_client.create_order(
                    symbol=symbol,
                    type='limit',
                    side=side,
                    amount=amount,
                    price=price
                )
                
                # Check fill ratio
                fill_ratio = float(order['filled']) / float(order['amount'])
                if fill_ratio < self.min_fill_ratio:
                    logger.warning(
                        f"Low fill ratio on {exchange_client.name}: {fill_ratio:.2%}"
                    )
                    # Cancel order and retry
                    await exchange_client.cancel_order(order['id'], symbol)
                    retries += 1
                    continue
                    
                return order
                
            except Exception as e:
                logger.error(f"Error in single order execution: {e}")
                retries += 1
                await asyncio.sleep(0.1)
                
        return None
        
    async def _execute_iceberg_order(
        self,
        exchange_client: object,
        symbol: str,
        side: str,
        total_amount: float,
        chunk_size: float,
        price: float,
        max_retries: int
    ) -> Optional[Dict]:
        """Execute an iceberg order in chunks"""
        filled_amount = 0.0
        total_cost = 0.0
        orders = []
        
        remaining = total_amount
        while remaining > 0:
            chunk = min(chunk_size, remaining)
            order = await self._execute_single_order(
                exchange_client,
                symbol,
                side,
                chunk,
                price,
                max_retries
            )
            
            if not order:
                # Cancel all orders and return None
                for o in orders:
                    try:
                        await exchange_client.cancel_order(o['id'], symbol)
                    except Exception as e:
                        logger.error(f"Error canceling order: {e}")
                return None
                
            filled_amount += float(order['filled'])
            total_cost += float(order['filled']) * float(order['average'])
            orders.append(order)
            
            remaining = total_amount - filled_amount
            
            # Adjust price based on market movement
            if remaining > 0:
                try:
                    ticker = await exchange_client.fetch_ticker(symbol)
                    price = float(ticker['bid' if side == 'sell' else 'ask'])
                except Exception as e:
                    logger.error(f"Error fetching ticker: {e}")
                    
        # Combine orders into single result
        return {
            'id': orders[0]['id'],
            'symbol': symbol,
            'side': side,
            'type': 'iceberg',
            'amount': total_amount,
            'filled': filled_amount,
            'average': total_cost / filled_amount if filled_amount > 0 else 0,
            'status': 'closed',
            'timestamp': datetime.now().timestamp() * 1000,
            'orders': orders
        } 