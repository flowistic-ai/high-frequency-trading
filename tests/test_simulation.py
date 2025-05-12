import pytest
from crypto_hft_tool.simulation import TradeSimulator
from crypto_hft_tool.config import FEES

def test_simulator_zero_spread():
    sim = TradeSimulator()
    # same buy & sell price ⇒ PnL = -(buy_fee + sell_fee)
    price = 100.0
    amt = 1.0
    pnl = sim.simulate_trade(
        symbol="TEST",
        buy_exchange="binance",
        buy_price=price,
        sell_exchange="kraken",
        sell_price=price,
        amount=amt,
    )
    expected = price * amt * (1 - FEES["kraken"]["maker"]) - price * amt * (1 + FEES["binance"]["taker"])
    assert pytest.approx(pnl, rel=1e-9) == expected

def test_simulator_profitable():
    sim = TradeSimulator()
    buy_price = 100.0
    sell_price = 101.0
    amt = 2.0
    pnl = sim.simulate_trade(
        symbol="TEST",
        buy_exchange="kraken",
        buy_price=buy_price,
        sell_exchange="binance",
        sell_price=sell_price,
        amount=amt,
    )
    # Manually compute expected
    cost = buy_price * amt
    buy_fee = cost * FEES["kraken"]["taker"]
    proceeds = sell_price * amt
    sell_fee = proceeds * FEES["binance"]["maker"]
    expected = proceeds - sell_fee - (cost + buy_fee)
    assert pytest.approx(pnl, rel=1e-9) == expected
