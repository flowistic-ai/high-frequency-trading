import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from .config import data_folder

def generate_sample_data(symbol: str, num_rows: int = 1000):
    """Generate synthetic order book data for testing."""
    # Base prices (approximate market prices)
    base_prices = {
        "BTC/USDT": 60000,
        "ETH/USDT": 3000
    }
    base_price = base_prices.get(symbol, 100)
    
    # Generate timestamps
    start_time = datetime.now() - timedelta(hours=num_rows/60)  # 1 minute intervals
    timestamps = [int((start_time + timedelta(minutes=i)).timestamp()) for i in range(num_rows)]
    
    # Generate price movements with some randomness
    price_movement = np.random.normal(0, 0.001, num_rows)  # Small random movements
    price_multiplier = np.cumprod(1 + price_movement)  # Cumulative effect
    
    # Generate data for each exchange
    data = []
    for i in range(num_rows):
        current_price = base_price * price_multiplier[i]
        
        # Add some spread between exchanges
        binance_spread = np.random.normal(0.5, 0.1)  # Average 0.5 USDT spread
        kraken_spread = np.random.normal(-0.5, 0.1)  # Opposite direction
        
        # Generate order book data
        row = {
            'timestamp': timestamps[i],
            'binance_bid': current_price + kraken_spread,
            'binance_ask': current_price + kraken_spread + 1.0,  # 1.0 USDT spread
            'kraken_bid': current_price + binance_spread,
            'kraken_ask': current_price + binance_spread + 1.0,  # 1.0 USDT spread
        }
        data.append(row)
    
    return pd.DataFrame(data)

def save_sample_data():
    """Generate and save sample data for all configured symbols."""
    # Create processed directory if it doesn't exist
    processed_dir = os.path.join(data_folder, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    
    # Generate data for each symbol
    symbols = ["BTC/USDT", "ETH/USDT"]
    for symbol in symbols:
        df = generate_sample_data(symbol)
        output_file = os.path.join(processed_dir, f"{symbol.replace('/', '_')}.csv")
        df.to_csv(output_file, index=False)
        print(f"Generated sample data for {symbol} at {output_file}")

if __name__ == "__main__":
    save_sample_data() 