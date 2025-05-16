import asyncio
import json
import logging
from typing import Dict, Optional, Set
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
import websockets
from sortedcontainers import SortedDict

from .config import WS_ENDPOINTS, SYMBOLS

logger = logging.getLogger(__name__)

class OrderBook:
    def __init__(self, depth: int = 10):
        self.bids = SortedDict()  # Price -> Amount
        self.asks = SortedDict()  # Price -> Amount
        self.depth = depth
        self.last_update = None
        
    def update(self, side: str, price: Decimal, amount: Decimal):
        """Update orderbook side at price level"""
        book = self.bids if side == 'bids' else self.asks
        if amount == 0:
            book.pop(price, None)
        else:
            book[price] = amount
        self.last_update = datetime.now()
        
    def get_top(self) -> Dict[str, Decimal]:
        """Get top of book prices"""
        return {
            'bid': self.bids.peekitem(-1)[0] if self.bids else Decimal('0'),
            'ask': self.asks.peekitem(0)[0] if self.asks else Decimal('inf')
        }

class OrderbookManager:
    def __init__(self):
        self.books: Dict[str, Dict[str, OrderBook]] = defaultdict(dict)
        self.subscriptions: Set[str] = set()
        self.ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.update_handlers = {
            'binance': self._handle_binance_update,
            'kraken': self._handle_kraken_update
        }
        
    def _init_orderbook(self, exchange: str, symbol: str):
        """Initialize orderbook for symbol"""
        if symbol not in self.books[exchange]:
            self.books[exchange][symbol] = OrderBook()
            
    async def _connect_binance(self):
        """Connect to Binance websocket"""
        streams = [f"{s.lower().replace('/', '')}@depth@100ms" 
                  for s in SYMBOLS]
        ws_url = f"{WS_ENDPOINTS['binance']}/stream?streams={'/'.join(streams)}"
        
        try:
            self.ws_connections['binance'] = await websockets.connect(ws_url)
            logger.info("Connected to Binance websocket")
        except Exception as e:
            logger.error(f"Failed to connect to Binance websocket: {e}")
            raise
            
    async def _connect_kraken(self):
        """Connect to Kraken websocket"""
        ws_url = WS_ENDPOINTS['kraken']
        try:
            self.ws_connections['kraken'] = await websockets.connect(ws_url)
            
            # Subscribe to orderbook updates
            subscribe_message = {
                "event": "subscribe",
                "pair": SYMBOLS,
                "subscription": {
                    "name": "book",
                    "depth": 10
                }
            }
            await self.ws_connections['kraken'].send(json.dumps(subscribe_message))
            logger.info("Connected to Kraken websocket")
        except Exception as e:
            logger.error(f"Failed to connect to Kraken websocket: {e}")
            raise
            
    async def _handle_binance_update(self, msg: Dict):
        """Process Binance orderbook update"""
        try:
            symbol = msg['s']
            self._init_orderbook('binance', symbol)
            book = self.books['binance'][symbol]
            
            # Update bids
            for bid in msg['b']:
                price = Decimal(bid[0])
                amount = Decimal(bid[1])
                book.update('bids', price, amount)
                
            # Update asks
            for ask in msg['a']:
                price = Decimal(ask[0])
                amount = Decimal(ask[1])
                book.update('asks', price, amount)
                
        except Exception as e:
            logger.error(f"Error processing Binance update: {e}")
            
    async def _handle_kraken_update(self, msg: Dict):
        """Process Kraken orderbook update"""
        try:
            if isinstance(msg, list) and len(msg) >= 4:
                symbol = msg[3]
                self._init_orderbook('kraken', symbol)
                book = self.books['kraken'][symbol]
                
                # Update bids
                if 'b' in msg[1]:
                    for bid in msg[1]['b']:
                        price = Decimal(bid[0])
                        amount = Decimal(bid[1])
                        book.update('bids', price, amount)
                        
                # Update asks
                if 'a' in msg[1]:
                    for ask in msg[1]['a']:
                        price = Decimal(ask[0])
                        amount = Decimal(ask[1])
                        book.update('asks', price, amount)
                        
        except Exception as e:
            logger.error(f"Error processing Kraken update: {e}")
            
    async def _process_messages(self, exchange: str):
        """Process incoming websocket messages"""
        while True:
            try:
                if exchange not in self.ws_connections:
                    await self._connect(exchange)
                    continue
                    
                msg = await self.ws_connections[exchange].recv()
                msg = json.loads(msg)
                await self.update_handlers[exchange](msg)
                
            except websockets.ConnectionClosed:
                logger.warning(f"{exchange} websocket connection closed. Reconnecting...")
                await self._connect(exchange)
            except Exception as e:
                logger.error(f"Error processing {exchange} message: {e}")
                await asyncio.sleep(1)
                
    async def _connect(self, exchange: str):
        """Connect to exchange websocket"""
        connect_func = getattr(self, f"_connect_{exchange}")
        await connect_func()
        
    def get_orderbook(self, exchange: str, symbol: str) -> Optional[Dict[str, Decimal]]:
        """Get current top of book"""
        try:
            if exchange in self.books and symbol in self.books[exchange]:
                book = self.books[exchange][symbol]
                if book.last_update:
                    age = (datetime.now() - book.last_update).total_seconds()
                    if age > 5:  # Data older than 5 seconds
                        logger.warning(f"Stale orderbook data for {exchange}:{symbol}")
                        return None
                return book.get_top()
            return None
        except Exception as e:
            logger.error(f"Error getting orderbook for {exchange}:{symbol}: {e}")
            return None
            
    async def start(self):
        """Start orderbook managers for all exchanges"""
        tasks = []
        for exchange in ['binance', 'kraken']:
            task = asyncio.create_task(self._process_messages(exchange))
            tasks.append(task)
        await asyncio.gather(*tasks)
        
    async def stop(self):
        """Close all websocket connections"""
        for exchange, ws in self.ws_connections.items():
            try:
                await ws.close()
                logger.info(f"Closed {exchange} websocket connection")
            except Exception as e:
                logger.error(f"Error closing {exchange} connection: {e}") 