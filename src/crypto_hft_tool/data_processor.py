import os
import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class DataProcessor:
    def __init__(self, raw_data_dir="data/raw", processed_data_dir="data/processed"):
        self.raw_data_dir = Path(raw_data_dir)
        self.processed_data_dir = Path(processed_data_dir)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)

    def normalize_orderbook_data(self, symbol: str):
        """Normalize raw orderbook data into a standardized format.
        
        Expected input format (raw data):
        - timestamp: Unix timestamp
        - exchange: 'binance' or 'kraken'
        - bids: List of [price, size] pairs
        - asks: List of [price, size] pairs
        
        Output format:
        - timestamp: Unix timestamp
        - binance_bid: Top bid price from Binance
        - binance_ask: Top ask price from Binance
        - kraken_bid: Top bid price from Kraken
        - kraken_ask: Top ask price from Kraken
        """
        try:
            # Read raw data
            raw_file = self.raw_data_dir / f"{symbol.replace('/', '_')}_raw.csv"
            if not raw_file.exists():
                logger.error(f"Raw data file not found: {raw_file}")
                return None

            df = pd.read_csv(raw_file)
            
            # Initialize empty lists for normalized data
            normalized_data = {
                'timestamp': [],
                'binance_bid': [],
                'binance_ask': [],
                'kraken_bid': [],
                'kraken_ask': []
            }

            # Process each row
            for _, row in df.iterrows():
                timestamp = row['timestamp']
                
                # Extract top of book for each exchange
                for exchange in ['binance', 'kraken']:
                    if row['exchange'] == exchange:
                        # Get top bid and ask
                        bids = eval(row['bids'])  # Convert string representation to list
                        asks = eval(row['asks'])
                        
                        top_bid = bids[0][0] if bids else None
                        top_ask = asks[0][0] if asks else None
                        
                        normalized_data[f'{exchange}_bid'].append(top_bid)
                        normalized_data[f'{exchange}_ask'].append(top_ask)
                
                normalized_data['timestamp'].append(timestamp)

            # Create DataFrame and sort by timestamp
            normalized_df = pd.DataFrame(normalized_data)
            normalized_df = normalized_df.sort_values('timestamp')
            
            # Save processed data
            output_file = self.processed_data_dir / f"{symbol.replace('/', '_')}.csv"
            normalized_df.to_csv(output_file, index=False)
            logger.info(f"Processed data saved to {output_file}")
            
            return normalized_df

        except Exception as e:
            logger.error(f"Error processing data for {symbol}: {str(e)}")
            return None

    def process_all_symbols(self, symbols):
        """Process all symbols in the raw data directory."""
        for symbol in symbols:
            logger.info(f"Processing {symbol}...")
            self.normalize_orderbook_data(symbol)

if __name__ == "__main__":
    # Example usage
    processor = DataProcessor()
    symbols = ["BTC/USDT", "ETH/USDT"]
    processor.process_all_symbols(symbols) 