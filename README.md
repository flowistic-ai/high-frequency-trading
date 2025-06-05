# Crypto HFT Tool

A sophisticated High-Frequency Trading (HFT) tool designed for cryptocurrency markets, focusing on cross-exchange statistical arbitrage between major exchanges like Binance and Kraken. The system identifies and exploits price discrepancies across exchanges in real-time.

## Overview

This project implements a comprehensive cryptocurrency trading system that combines real-time market data processing, advanced statistical arbitrage strategies, and a modern web-based dashboard for monitoring and control. The system is built with scalability and performance in mind, utilizing FastAPI for the backend, React for the frontend, and modern Python technologies for the trading engine.

## Core Features

### Cross-Exchange Arbitrage
- Real-time price monitoring across multiple exchanges (Binance, Kraken)
- Automated trade execution when price discrepancies exceed thresholds
- Multi-exchange order routing and execution
- Slippage and fee-aware trading decisions
- Cross-exchange transfer cost consideration

### Statistical Arbitrage
- Z-score based spread analysis between exchanges
- Volume-weighted signal adjustment
- Momentum-based signal enhancement
- Adaptive threshold calculation based on:
  - Market volatility
  - Trading volume
  - Time of day
  - Momentum indicators
  - Exchange-specific liquidity
- Self-adjusting parameters based on market conditions

## Technical Architecture

### Backend (FastAPI)
- RESTful API endpoints for market data, trading signals, and simulation results
- WebSocket support for real-time data streaming from multiple exchanges
- CORS-enabled for frontend integration
- Modular design with separate components for:
  - Data provision
  - Signal processing
  - Trade execution
  - Orderbook management
  - Performance monitoring

### Frontend (React)
- Modern React-based dashboard for monitoring trading activity
- Material-UI components for consistent design
- Interactive charts using Plotly.js and Recharts
- Real-time data updates using React Query
- Performance metrics visualization
- Trade history and leaderboard
- Responsive design for all device sizes

## Project Structure

```
crypto_hft_tool/
├── src/
│   └── crypto_hft_tool/
│       ├── main.py                 # FastAPI application and endpoints
│       ├── config.py              # Configuration management
│       ├── data_provider.py       # Market data handling
│       ├── live_trader.py         # Live trading implementation
│       ├── backtest.py            # Backtesting framework
│       ├── signals.py             # Base signal generation
│       ├── enhanced_signals.py    # Advanced signal strategies
│       ├── execution_manager.py   # Order execution handling
│       ├── orderbook_manager.py   # Orderbook processing
│       └── data_pipeline.py       # Data processing pipeline
├── hft-frontend/                  # React frontend application
├── tests/                         # Test suite
├── docs/                          # Documentation
└── data/                          # Data storage
```

## Requirements

### Backend
- Python 3.9 or higher
- Dependencies listed in `requirements.txt`:
  - ccxt >= 4.0.0
  - websockets >= 11.0.0
  - pandas >= 2.0.0
  - numpy >= 1.24.0
  - fastapi
  - uvicorn
  - gunicorn
  - and more...

### Frontend
- Node.js 14 or higher
- Dependencies listed in `hft-frontend/package.json`:
  - React 18
  - Material-UI
  - Plotly.js
  - Recharts
  - React Query
  - and more...

## Installation

### Backend Setup
1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd crypto_hft_tool
   ```

2. Install dependencies:
   You can install dependencies using either pip or uv:

   **Option 1: pip**
   ```bash
   python -m venv venv
   source venv/bin/activate  
   # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

   **Option 2: uv**
   ```bash
   uv sync
   ```

4. Set up environment variables:
   Create a `.env` file with your configuration (see `.env.example` for reference)

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd hft-frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

## Usage

### Running the Backend API

You can run the backend using either `uvicorn` directly or via [`uv`](https://github.com/astral-sh/uv), a modern Python package manager that supports PEP 582 and virtual environments out-of-the-box.

**Option 1: Using uvicorn directly**
```bash
uvicorn src.crypto_hft_tool.main:app --reload
```

**Option 2: Using uv**
```bash
uv pip install uvicorn  # if not already installed
uvicorn src.crypto_hft_tool.main:app --reload
```
Or, if you want to run it via uv's run command:
```bash
uv run uvicorn src.crypto_hft_tool.main:app --reload
```

### Running the Frontend

```bash
cd hft-frontend
npm start
```

### Running Live Trading

```bash
python src/crypto_hft_tool/run_live.py
```

### Running Backtests

```bash
python src/crypto_hft_tool/backtest.py
```

## API Endpoints

- `GET /api/v1/market_data/all` - Get market data for all symbols
- `GET /api/v1/market_data/{symbol}` - Get market data for specific symbol
- `GET /api/v1/simulation/status` - Get current simulation status
- `GET /api/v1/simulation/trades` - Get recent trades
- `GET /api/v1/simulation/leaderboard` - Get performance leaderboard

## Development

### Running Tests

```bash
# Backend tests
pytest tests/

# Frontend tests
cd hft-frontend
npm test
```

### Code Style

The project follows PEP 8 guidelines for Python code and ESLint configuration for React code.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the terms of the included LICENSE file.

## Disclaimer

This software is for educational and research purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred through the use of this software.
