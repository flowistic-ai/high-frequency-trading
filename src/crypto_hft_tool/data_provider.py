import os
import pandas as pd
import ccxt
from typing import Optional, Dict # Import Optional and Dict for type hinting
from .config import data_folder # SYMBOLS is not used here, it's used by dashboard

class DataProvider:
    """
    Provides top-of-book data either live (CCXT) or from historical CSVs.
    Handles basic error reporting.
    """
    def __init__(self, live: bool = True, backtest_dir: str = None):
        self.live = live
        self.error = None  # To store any fetch/init error
        
        if self.live:
            try:
                # Add options for timeout and User-Agent if needed, adjustForTimeDifference can be helpful
                common_params = {"enableRateLimit": True, "options": {"adjustForTimeDifference": True}}
                self.binance = ccxt.binance(common_params)
                self.kraken  = ccxt.kraken(common_params)
                # Optionally, test connection by fetching markets (can be slow)
                # self.binance.fetch_markets()
                # self.kraken.fetch_markets()
            except Exception as e:
                self.live = False # Fallback or indicate error state
                self.error = f"Failed to initialize CCXT clients: {str(e)}"
        else:
            self.backtest_dir = backtest_dir or os.path.join(data_folder, "processed")
            self._dfs = {}
            self._ptrs = {}
            if not os.path.isdir(self.backtest_dir):
                 self.error = f"Backtest directory not found: {self.backtest_dir}"

    def get_top_of_book(self, symbol: str) -> Optional[Dict]:
        """
        Returns a dict: {'binance': {'bid': float, 'ask': float}, 'kraken': {'bid': float, 'ask': float}}
        Returns None if data cannot be fetched, and sets self.error.
        """
        self.error = None # Clear previous error for this call

        if self.live:
            if not hasattr(self, 'binance') or not hasattr(self, 'kraken'):
                 self.error = "CCXT clients not initialized for live mode."
                 return None
            try:
                # kraken_symbol = symbol # No longer needed, use symbol directly
                # if symbol == "BTC/USDT": # Kraken uses XBT for Bitcoin
                #     kraken_symbol = "XBT/USDT" # Removed this forced conversion
                
                bkb = self.binance.fetch_order_book(symbol, limit=1)
                # Use the original symbol for Kraken directly
                krb = self.kraken.fetch_order_book(symbol, limit=1)

                if not bkb or not bkb.get('bids') or not bkb['bids'] or not bkb.get('asks') or not bkb['asks']:
                    raise ValueError(f"Binance order book for {symbol} is empty or malformed.")
                if not krb or not krb.get('bids') or not krb['bids'] or not krb.get('asks') or not krb['asks']:
                    raise ValueError(f"Kraken order book for {symbol} is empty or malformed.")

                return {
                    'binance': {'bid': bkb['bids'][0][0], 'ask': bkb['asks'][0][0]},
                    'kraken' : {'bid': krb['bids'][0][0], 'ask': krb['asks'][0][0]},
                }
            except ccxt.NetworkError as e:
                self.error = f"NetworkError fetching live data for {symbol}: {str(e)}"
                return None
            except ccxt.ExchangeError as e:
                self.error = f"ExchangeError fetching live data for {symbol}: {str(e)}"
                return None
            except Exception as e:
                self.error = f"General error fetching live data for {symbol}: {str(e)}"
                return None
        else: # Backtest mode from CSV
            if hasattr(self, 'error') and self.error and "Backtest directory not found" in self.error:
                return None # Don't try to read if directory was confirmed missing

            if symbol not in self._dfs:
                try:
                    path = os.path.join(self.backtest_dir, f"{symbol.replace('/', '_')}.csv")
                    if not os.path.exists(path):
                        self.error = f"Backtest file not found: {path}"
                        self._dfs[symbol] = None # Mark as tried
                        return None
                    
                    df = pd.read_csv(path)
                    if df.empty:
                        self.error = f"Backtest file is empty: {path}"
                        self._dfs[symbol] = None 
                        return None
                    
                    required_cols = ['binance_bid', 'binance_ask', 'kraken_bid', 'kraken_ask']
                    if not all(col in df.columns for col in required_cols):
                        self.error = f"Backtest file {path} missing one or more required columns: {required_cols}"
                        self._dfs[symbol] = None
                        return None

                    self._dfs[symbol] = df
                    self._ptrs[symbol] = 0
                except Exception as e:
                    self.error = f"Error loading backtest data for {symbol} from {path}: {str(e)}"
                    self._dfs[symbol] = None # Mark as load-failed
                    return None
            
            if self._dfs.get(symbol) is None:
                # Error should have been set during the load attempt or file not found
                if not self.error: # If somehow no error was set, set a generic one
                    self.error = f"Failed to load backtest data for {symbol}, DataFrame is None."
                return None

            df = self._dfs[symbol]
            idx = self._ptrs[symbol]

            if idx >= len(df):
                self.error = f"End of backtest data reached for {symbol} (index {idx} >= length {len(df)})."
                # Return last known good data or None
                # For dashboard, let's return None to stop updates once data ends.
                return None 

            row = df.iloc[idx]
            self._ptrs[symbol] = idx + 1 # Advance pointer for next call

            return {
                'binance': {'bid': row['binance_bid'], 'ask': row['binance_ask']},
                'kraken' : {'bid': row['kraken_bid'], 'ask': row['kraken_ask']},
            } 