import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export interface MarketData {
  timestamp: string;
  symbol: string;
  binance: {
    bid: number;
    ask: number;
  };
  kraken: {
    bid: number;
    ask: number;
  };
  spread: number;
  z_score?: number;
  error?: string;
}

export interface SimulationStatus {
  total_pnl: number;
  total_trades: number;
  z_score_threshold: number;
  trade_amount: number;
  exit_z_threshold: number;
  stop_loss_amount: number;
}

export interface Trade {
  timestamp: string;
  symbol: string;
  buy_exchange: string;
  buy_price: number;
  sell_exchange: string;
  sell_price: number;
  amount: number;
  pnl: number;
}

const api = {
  getAllMarketData: async () => {
    const response = await axios.get(`${API_BASE_URL}/market_data/all`);
    return response.data;
  },

  getMarketData: async (symbol: string) => {
    const response = await axios.get(`${API_BASE_URL}/market_data/${symbol}`);
    return response.data;
  },

  getSimulationStatus: async () => {
    const response = await axios.get(`${API_BASE_URL}/simulation/status`);
    return response.data;
  },

  getRecentTrades: async (limit: number = 10) => {
    const response = await axios.get(`${API_BASE_URL}/simulation/trades?limit=${limit}`);
    return response.data;
  },

  getLeaderboard: async () => {
    const response = await axios.get(`${API_BASE_URL}/simulation/leaderboard`);
    return response.data;
  }
};

export default api; 