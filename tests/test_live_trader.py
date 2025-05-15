import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from crypto_hft_tool.live_trader import LiveTrader
from crypto_hft_tool.config import ZSCORE_SETTINGS, TRADE_SETTINGS

@pytest.fixture
async def trader():
    """Create a LiveTrader instance with mocked exchanges"""
    with patch('ccxt.async_support.binance') as mock_binance, \
         patch('ccxt.async_support.kraken') as mock_kraken:
        
        # Setup mock exchanges
        mock_binance.return_value = MagicMock()
        mock_binance.return_value.fetch_balance = AsyncMock(return_value={'free': {'BTC': 1.0}})
        mock_binance.return_value.load_markets = AsyncMock()
        
        mock_kraken.return_value = MagicMock()
        mock_kraken.return_value.fetch_balance = AsyncMock(return_value={'free': {'BTC': 1.0}})
        mock_kraken.return_value.load_markets = AsyncMock()
        
        trader = LiveTrader()
        yield trader
        
        # Cleanup
        await trader.shutdown()

class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

@pytest.mark.asyncio
async def test_initialization(trader):
    """Test trader initialization"""
    assert trader.risk_manager is not None
    assert trader.fee_manager is not None
    assert len(trader.ztrackers) == len(TRADE_SETTINGS['position_sizing']['min_size'])
    assert all(tf in ZSCORE_SETTINGS['windows'] for tf in ZSCORE_SETTINGS['thresholds']['entry'])

@pytest.mark.asyncio
async def test_orderbook_fetching(trader):
    """Test orderbook fetching with mocked data"""
    mock_orderbook = {
        'bids': [[30000.0, 1.0]],
        'asks': [[30001.0, 1.0]]
    }
    
    with patch.object(trader.exchanges['binance'], 'fetch_order_book',
                     new_callable=AsyncMock, return_value=mock_orderbook):
        book = await trader._get_orderbook('binance', 'BTC/USDT')
        
        assert book is not None
        assert isinstance(book['bid'], Decimal)
        assert isinstance(book['ask'], Decimal)
        assert float(book['bid']) == 30000.0
        assert float(book['ask']) == 30001.0
        assert isinstance(book['timestamp'], datetime)

@pytest.mark.asyncio
async def test_trade_conditions(trader):
    """Test trade condition checking"""
    books = {
        'binance': {
            'bid': Decimal('30000.0'),
            'ask': Decimal('30001.0'),
            'timestamp': datetime.now()
        },
        'kraken': {
            'bid': Decimal('29999.0'),
            'ask': Decimal('30000.0'),
            'timestamp': datetime.now()
        }
    }
    
    # First call should return None as not enough data for Z-score
    trade_params = await trader._check_trade_conditions('BTC/USDT', books, datetime.now())
    assert trade_params is None
    
    # Add some spread data to build up Z-score history
    for i in range(50):
        spread = float(books['binance']['ask'] - books['kraken']['bid'])
        trader.ztrackers['BTC/USDT'].add(spread, datetime.now())
    
    # Now should get valid trade parameters
    trade_params = await trader._check_trade_conditions('BTC/USDT', books, datetime.now())
    
    assert trade_params is not None
    assert 'timeframe' in trade_params
    assert 'z_score' in trade_params
    assert 'direction' in trade_params
    assert 'profit' in trade_params
    assert trade_params['direction'] in [1, -1]
    assert trade_params['profit'] > 0

@pytest.mark.asyncio
async def test_order_execution(trader):
    """Test order execution with mocked responses"""
    mock_order = {
        'id': '123',
        'status': 'closed',
        'filled': 0.001
    }
    
    with patch.object(trader.exchanges['binance'], 'create_order',
                     new_callable=AsyncMock, return_value=mock_order):
        order = await trader._execute_order(
            'binance', 'BTC/USDT', 'buy', 0.001, 30000.0
        )
        
        assert order is not None
        assert order['id'] == '123'
        assert order['status'] == 'closed'
        
        # Check metrics updated
        assert len(trader.metrics['latency_ms']) == 1
        assert trader.metrics['errors_count'] == 0

@pytest.mark.asyncio
async def test_full_trade_execution(trader):
    """Test full trade execution flow"""
    books = {
        'binance': {
            'bid': Decimal('30000.0'),
            'ask': Decimal('30001.0'),
            'timestamp': datetime.now()
        },
        'kraken': {
            'bid': Decimal('29999.0'),
            'ask': Decimal('30000.0'),
            'timestamp': datetime.now()
        }
    }
    
    # Setup mock orders
    mock_order = {
        'id': '123',
        'status': 'closed',
        'filled': 0.001
    }
    
    with patch.object(trader.exchanges['binance'], 'create_order',
                     new_callable=AsyncMock, return_value=mock_order), \
         patch.object(trader.exchanges['kraken'], 'create_order',
                     new_callable=AsyncMock, return_value=mock_order):
        
        # Build up Z-score history
        for i in range(50):
            spread = float(books['binance']['ask'] - books['kraken']['bid'])
            trader.ztrackers['BTC/USDT'].add(spread, datetime.now())
        
        # Get trade parameters
        trade_params = await trader._check_trade_conditions(
            'BTC/USDT', books, datetime.now()
        )
        
        assert trade_params is not None
        
        # Execute trade
        success = await trader._execute_trade('BTC/USDT', trade_params, books)
        
        assert success
        assert trader.metrics['trades_count'] == 1
        assert trader.metrics['errors_count'] == 0
        assert len(trader.metrics['latency_ms']) == 2  # Two orders executed
        assert trader.last_trade_time['BTC/USDT'] is not None

@pytest.mark.asyncio
async def test_error_handling(trader):
    """Test error handling during order execution"""
    with patch.object(trader.exchanges['binance'], 'create_order',
                     new_callable=AsyncMock, side_effect=Exception("API Error")):
        order = await trader._execute_order(
            'binance', 'BTC/USDT', 'buy', 0.001, 30000.0
        )
        
        assert order is None
        assert trader.metrics['errors_count'] == 1

@pytest.mark.asyncio
async def test_shutdown(trader):
    """Test clean shutdown"""
    await trader.shutdown()
    
    # Verify exchanges were closed
    for exchange in trader.exchanges.values():
        assert exchange.close.called 