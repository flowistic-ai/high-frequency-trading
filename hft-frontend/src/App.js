import React, { useState, useEffect } from 'react'; // Removed useCallback as fetchData will be handled by react-query
import Plot from 'react-plotly.js';
import './App.css';
import axios from 'axios';
import { QueryClient, QueryClientProvider, useQuery } from 'react-query';

// Use local backend for development
const API_BASE_URL = 'http://localhost:8000'; // Ensure no trailing slash if /api/v1 is in paths
const SYMBOLS = [
  "BTC/USDT", "ETH/USDT"
];
const REFRESH_INTERVAL = 2000; // Milliseconds
const MAX_HISTORY_POINTS = 300;

// API service object using axios
const api = {
  getMarketData: async (symbol) => {
    try {
      const { data } = await axios.get(`${API_BASE_URL}/api/v1/market_data/${encodeURIComponent(symbol)}`);
      return data;
    } catch (error) {
      console.error(`Error fetching market data for ${symbol}:`, error);
      return null;
    }
  },
  getSimulationStatus: async () => {
    try {
      const { data } = await axios.get(`${API_BASE_URL}/api/v1/simulation/status`);
      return data;
    } catch (error) {
      console.error('Error fetching simulation status:', error);
      return null;
    }
  },
  getRecentTrades: async (limit = 10) => {
    try {
      const { data } = await axios.get(`${API_BASE_URL}/api/v1/simulation/trades?limit=${limit}`);
      return data.trades || [];
    } catch (error) {
      console.error('Error fetching recent trades:', error);
      return [];
    }
  },
  getLeaderboard: async () => {
    try {
      const { data } = await axios.get(`${API_BASE_URL}/api/v1/simulation/leaderboard`);
      return data.leaderboard || [];
    } catch (error) {
      console.error('Error fetching leaderboard:', error);
      return [];
    }
  },
  getAllMarketData: async () => {
    try {
      const { data } = await axios.get(`${API_BASE_URL}/api/v1/market_data/all`);
      return data.data || {};
    } catch (error) {
      console.error('Error fetching all market data:', error);
      return {};
    }
  },
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      staleTime: 0,
      cacheTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchOnMount: true,
    },
  },
});

function AppContent() { // Renamed original App to AppContent
  const [selectedSymbol, setSelectedSymbol] = useState(SYMBOLS[0]);
  const [history, setHistory] = useState({
    timestamp: [],
    mid_price: [],
    raw_zscore: [],
    adaptive_threshold: [],
    signal_strength: [],
    momentum_score: [],
  });

  const { data: marketData, error: marketDataError, isLoading: marketDataLoading } = useQuery(
    ['marketData', selectedSymbol], // Query key includes selectedSymbol
    () => api.getMarketData(selectedSymbol),
    {
      refetchInterval: REFRESH_INTERVAL,
      onError: (err) => console.error("Market Data fetch error:", err),
    }
  );

  const { data: simulationStatus, error: simStatusError, isLoading: simStatusLoading } = useQuery(
    'simulationStatus',
    api.getSimulationStatus,
    {
      refetchInterval: REFRESH_INTERVAL,
      onError: (err) => console.error("Simulation Status fetch error:", err),
    }
  );

  const { data: recentTrades, error: tradesError, isLoading: tradesLoading } = useQuery(
    'recentTrades',
    () => api.getRecentTrades(10),
    {
      refetchInterval: REFRESH_INTERVAL,
      onError: (err) => console.error("Recent Trades fetch error:", err),
    }
  );

  const { data: leaderboard, error: leaderboardError, isLoading: leaderboardLoading } = useQuery(
    'leaderboard',
    api.getLeaderboard,
    {
      refetchInterval: REFRESH_INTERVAL,
      onError: (err) => console.error("Leaderboard fetch error:", err),
    }
  );

  const { data: allMarketData, error: allMarketDataError, isLoading: allMarketDataLoading } = useQuery(
    'allMarketData',
    api.getAllMarketData,
    {
      refetchInterval: REFRESH_INTERVAL,
      onError: (err) => console.error("All Market Data fetch error:", err),
    }
  );

  // useEffect to update history when marketData for selectedSymbol changes
  useEffect(() => {
    if (marketData) {
      console.log("Received market data:", marketData); // Debug log
      setHistory(prevHistory => {
        const newTimestamp = [...prevHistory.timestamp, new Date(marketData.timestamp)];
        const newMidPrice = [...prevHistory.mid_price, marketData.mid_price || 0];
        const newRawZScore = [...prevHistory.raw_zscore, marketData.raw_zscore || 0];
        const newAdaptiveThreshold = [...prevHistory.adaptive_threshold, marketData.adaptive_threshold || 0];
        const newSignalStrength = [...prevHistory.signal_strength, marketData.signal_strength || 0];
        const newMomentumScore = [...prevHistory.momentum_score, marketData.momentum_score || 0];

        // Keep only the last MAX_HISTORY_POINTS
        const trim = (arr) => arr.slice(-MAX_HISTORY_POINTS);

        return {
          timestamp: trim(newTimestamp),
          mid_price: trim(newMidPrice),
          raw_zscore: trim(newRawZScore),
          adaptive_threshold: trim(newAdaptiveThreshold),
          signal_strength: trim(newSignalStrength),
          momentum_score: trim(newMomentumScore),
        };
      });
    }
  }, [marketData]);

  // Reset history when selectedSymbol changes
  useEffect(() => {
    console.log("Symbol changed to:", selectedSymbol); // Debug log
    setHistory({
      timestamp: [],
      mid_price: [],
      raw_zscore: [],
      adaptive_threshold: [],
      signal_strength: [],
      momentum_score: [],
    });
  }, [selectedSymbol]);

  const isLoading = marketDataLoading || simStatusLoading || tradesLoading || leaderboardLoading || allMarketDataLoading;
  const combinedError = marketDataError || simStatusError || tradesError || leaderboardError || allMarketDataError;

  // Log errors for debugging
  useEffect(() => {
    if (combinedError) {
      console.error("Combined error state:", {
        marketDataError,
        simStatusError,
        tradesError,
        leaderboardError,
        allMarketDataError
      });
    }
  }, [combinedError, marketDataError, simStatusError, tradesError, leaderboardError, allMarketDataError]);

  // Log data updates for debugging
  useEffect(() => {
    if (marketData) {
      console.log("Market data update:", {
        symbol: marketData.symbol,
        timestamp: marketData.timestamp,
        signal: marketData.signal,
        signal_strength: marketData.signal_strength,
        raw_zscore: marketData.raw_zscore,
        mid_price: marketData.mid_price
      });
    }
  }, [marketData]);

  // Define Plotly layout (can be customized further)
  const commonLayout = {
    autosize: true,
    margin: { l: 60, r: 40, t: 60, b: 50 },
    paper_bgcolor: '#1a1a1a',
    plot_bgcolor: '#1a1a1a',
    font: { color: '#ffffff' },
    xaxis: { 
      gridcolor: '#333333',
      color: '#ffffff',
      title: 'Time',
      titlefont: { color: '#ffffff' }
    },
    yaxis: { 
      gridcolor: '#333333',
      color: '#ffffff',
      title: 'Value',
      titlefont: { color: '#ffffff' }
    },
    legend: { 
      orientation: "h",
      yanchor: "bottom",
      y: 1.02,
      xanchor: "right",
      x: 1,
      font: { color: '#ffffff' },
      bgcolor: '#1a1a1a',
      bordercolor: '#333333'
    },
    modebar: {
      bgcolor: '#1a1a1a',
      color: '#ffffff',
      activecolor: '#0197ae'
    }
  };

  const tradesTicker = (
    <div className="live-trades-ticker">
      <h2>Live Trades</h2>
      <div className="ticker-content" style={{ overflowX: 'auto', whiteSpace: 'nowrap', border: '1px solid #ccc', padding: '5px' }}>
        {recentTrades && recentTrades.length > 0 ? (
          recentTrades.map((trade, index) => (
            <span key={index} style={{ marginRight: '20px' }}>
              {trade.symbol} {trade.buy_exchange} &gt; {trade.sell_exchange} @ {trade.sell_price?.toFixed(4) || 'N/A'} (PnL: {trade.pnl?.toFixed(6) || 'N/A'})
            </span>
          ))
        ) : (
          <span>No live trades yet...</span>
        )}
      </div>
    </div>
  );

  const leaderboardTable = (
    <div className="leaderboard-section">
      <h2>Leaderboard</h2>
      {leaderboard && leaderboard.length > 0 && !leaderboard.every(entry => entry.trade_count === 0) ? (
        <table className="leaderboard-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Total PnL</th>
              <th>Trade Count</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.map((entry) => (
              <tr key={entry.symbol} className={entry.symbol === selectedSymbol ? 'selected-symbol-row' : ''}>
                <td>{entry.symbol}</td>
                <td className={entry.total_pnl > 0 ? 'pnl-positive' : entry.total_pnl < 0 ? 'pnl-negative' : ''}>
                  {entry.total_pnl?.toFixed(6) || '0.000000'}
                </td>
                <td>{entry.trade_count || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div>No trading activity yet...</div>
      )}
    </div>
  );

  // Add error display with more details
  const errorDisplay = combinedError && (
    <div className="error-display" style={{ color: 'red', padding: '10px', margin: '10px', border: '1px solid red' }}>
      <h3>Error Loading Data</h3>
      <pre>{JSON.stringify({
        marketDataError: marketDataError?.message || 'No error',
        simStatusError: simStatusError?.message || 'No error',
        tradesError: tradesError?.message || 'No error',
        leaderboardError: leaderboardError?.message || 'No error',
        allMarketDataError: allMarketDataError?.message || 'No error'
      }, null, 2)}</pre>
    </div>
  );

  // Add loading display with more context
  const loadingDisplay = isLoading && (
    <div className="loading-display" style={{ padding: '10px', margin: '10px', border: '1px solid #ccc' }}>
      <p>Loading data...</p>
      <ul>
        {marketDataLoading && <li>Market Data</li>}
        {simStatusLoading && <li>Simulation Status</li>}
        {tradesLoading && <li>Recent Trades</li>}
        {leaderboardLoading && <li>Leaderboard</li>}
        {allMarketDataLoading && <li>All Market Data</li>}
      </ul>
    </div>
  );

  // Add data validation display
  const dataValidationDisplay = marketData && (
    <div className="data-validation" style={{ padding: '10px', margin: '10px', border: '1px solid #ccc' }}>
      <h4>Data Validation</h4>
      <ul>
        <li>Symbol: {marketData.symbol}</li>
        <li>Timestamp: {marketData.timestamp}</li>
        <li>Mid Price: {marketData.mid_price?.toFixed(2) || 'N/A'}</li>
        <li>Signal: {marketData.signal}</li>
        <li>Signal Strength: {marketData.signal_strength?.toFixed(2) || 'N/A'}</li>
        <li>Z-Score: {marketData.raw_zscore?.toFixed(2) || 'N/A'}</li>
      </ul>
    </div>
  );

  const zScoreHeatmap = (
    <div className="zscore-heatmap-section">
      <h2>Signal Heatmap</h2>
      <div className="zscore-heatmap-legend">
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#ff6666'}}></span>Strong Sell Signal</div>
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#ffe066'}}></span>Weak Sell Signal</div>
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#b2f7ef'}}></span>Hold / Neutral</div>
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#66b3ff'}}></span>Weak Buy Signal</div>
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#3385ff'}}></span>Strong Buy Signal</div>
      </div>
      <div className="zscore-heatmap-grid">
        {SYMBOLS.map(sym => {
          const data = allMarketData && allMarketData[sym];
          const rawZ = data?.raw_zscore;
          const strength = data?.signal_strength;
          const threshold = data?.adaptive_threshold;
          let bg = '#b2f7ef'; // Neutral
          let textColor = '#222';

          if (typeof strength === 'number' && typeof threshold === 'number' && typeof rawZ === 'number') {
            if (strength >= threshold) { // Potential signal
              if (rawZ < 0) { // Buy signal potential
                bg = strength >= threshold * 1.5 ? '#3385ff' : '#66b3ff'; // Stronger if 1.5x threshold
                textColor = '#fff';
              } else { // Sell signal potential
                bg = strength >= threshold * 1.5 ? '#ff6666' : '#ffe066';
                textColor = strength >= threshold * 1.5 ? '#fff' : '#222';
              }
            } else { // No strong signal, color by Z-score direction if desired, or keep neutral
              // Optional: color based on raw Z for non-signal states
              // if (rawZ > 1.0) bg = '#ffe0cc'; // Mildly positive Z
              // else if (rawZ < -1.0) bg = '#cce0ff'; // Mildly negative Z
            }
          }
          
          return (
            <div
              key={sym}
              className="zscore-heatmap-cell"
              style={{ background: bg, color: textColor, border: sym === selectedSymbol ? '2px solid #0197ae' : '1px solid #ccc' }}
              onClick={() => setSelectedSymbol(sym)}
            >
              <div style={{ fontSize: 13, fontWeight: 'bold' }}>{sym}</div>
              <div style={{ fontSize: 12, marginTop: '3px' }}>
                {data ? (
                  <>
                    <div>Z: {rawZ?.toFixed(2) ?? 'N/A'}</div>
                    <div>Str: {strength?.toFixed(2) ?? 'N/A'}</div>
                    <div>Thr: {threshold?.toFixed(2) ?? 'N/A'}</div>
                  </>
                ) : 'Loading...'}
              </div>
              <div className="zscore-tooltip">
                {sym}: Click to view details<br/>
                Raw Z: {rawZ?.toFixed(3) ?? 'N/A'}<br/>
                Signal Strength: {strength?.toFixed(3) ?? 'N/A'}<br/>
                Adaptive Threshold: {threshold?.toFixed(3) ?? 'N/A'}<br/>
                Momentum: {data?.momentum_score?.toFixed(3) ?? 'N/A'}<br/>
                Signal: {data?.signal ?? 'N/A'} 
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="App">
      {errorDisplay}
      {loadingDisplay}
      {dataValidationDisplay}
      <header className="App-header">
        <div className="App-logo-container">
          <img src={process.env.PUBLIC_URL + '/flowistic-logo.png'} className="App-logo" alt="Flowistic Logo" />
          <h1>Crypto HFT Dashboard</h1>
        </div>
        <div style={{ margin: '10px 0' }}>
          <label htmlFor="symbol-select" style={{ color: '#0197ae', fontWeight: 600, marginRight: 8 }}>Symbol:</label>
          <select
            id="symbol-select"
            value={selectedSymbol}
            onChange={e => setSelectedSymbol(e.target.value)}
            style={{ fontSize: '1rem', padding: '4px 10px', borderRadius: 4, border: '1px solid #0197ae', color: '#0197ae', background: '#f8f2eb', fontWeight: 600 }}
          >
            {SYMBOLS.map(sym => (
              <option key={sym} value={sym}>{sym}</option>
            ))}
          </select>
        </div>
        <p style={{fontSize: '1rem', fontWeight: 'normal', margin: '5px 0 0 0'}}>
          Displaying: {selectedSymbol}
        </p>
      </header>
      <main className="App-main dashboard-container">
        {tradesTicker}
        {leaderboardTable}
        {zScoreHeatmap}
        <div className="status-metrics-section">
          {isLoading && <p>Loading data...</p>}
          {combinedError && <p className="error-message">Error fetching data: {combinedError.message}</p>}
          {!isLoading && !combinedError && marketData && !marketData.error && <p className="status-ok">Live Data Feed Running</p>}
          {marketData?.error && <p className="error-message">Provider Error for {selectedSymbol}: {marketData.error}</p>}

          <div className="metrics-container">
              {simulationStatus ? (
                <>
                  <div className="metric-item"><span>Total PnL:</span> {simulationStatus.total_pnl?.toFixed(6)}</div>
                  <div className="metric-item"><span>Total Trades:</span> {simulationStatus.total_trades}</div>
                  <div className="metric-item"><span>Win Rate:</span> {simulationStatus.win_rate?.toFixed(2)}%</div>
                  <div className="metric-item"><span>Avg PnL/Trade:</span> {simulationStatus.avg_pnl_per_trade?.toFixed(6)}</div>
                  <div className="metric-item"><span>Total Fees:</span> {simulationStatus.total_fees_paid?.toFixed(6)}</div>
                </>
              ) : <div className="metric-item">Loading PnL status...</div> }
          </div>
        </div>

        <div className="chart-section chart-section-prices">
          {history.timestamp.length > 0 ? (
            <Plot
              data={[
                {
                  x: history.timestamp,
                  y: history.mid_price,
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Mid Price',
                  line: { color: '#01DBB0', width: 2 },
                  hoverinfo: 'x+y'
                }
              ]}
              layout={{
                ...commonLayout,
                title: {
                  text: `Market Prices for ${selectedSymbol}`,
                  font: { color: '#ffffff' }
                },
                hovermode: 'x unified',
                yaxis: {
                  ...commonLayout.yaxis,
                  title: 'Price (USDT)',
                }
              }}
              style={{ width: '100%', height: '400px' }}
              useResizeHandler={true}
              config={{
                displayModeBar: true,
                responsive: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
              }}
            />
          ) : (
            <div className="loading-message">
              Waiting for price data for {selectedSymbol}...
            </div>
          )}
        </div>

        <div className="chart-section chart-section-signals">
          {history.timestamp.length > 0 ? (
            <Plot
              data={[
                {
                  x: history.timestamp,
                  y: history.raw_zscore,
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Z-Score',
                  line: { color: '#FFD700', width: 2 },
                  hoverinfo: 'x+y'
                },
                {
                  x: history.timestamp,
                  y: history.signal_strength,
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Signal Strength',
                  line: { color: '#0197ae', width: 2 },
                  hoverinfo: 'x+y'
                },
                {
                  x: history.timestamp,
                  y: history.adaptive_threshold,
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Adaptive Threshold',
                  line: { color: '#ff6b6b', width: 2, dash: 'dash' },
                  hoverinfo: 'x+y'
                }
              ]}
              layout={{
                ...commonLayout,
                title: {
                  text: `Trading Signals for ${selectedSymbol}`,
                  font: { color: '#ffffff' }
                },
                hovermode: 'x unified',
                yaxis: {
                  ...commonLayout.yaxis,
                  title: 'Signal Values',
                  zeroline: true,
                  zerolinecolor: '#666666'
                }
              }}
              style={{ width: '100%', height: '400px' }}
              useResizeHandler={true}
              config={{
                displayModeBar: true,
                responsive: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
              }}
            />
          ) : (
            <div className="loading-message">
              Waiting for signal data for {selectedSymbol}...
            </div>
          )}
        </div>

        <div className="trades-section">
          <h2>Recent Trades</h2>
          {recentTrades && recentTrades.length > 0 ? (
            <div className="trades-table-container">
              <table className="trades-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Symbol</th>
                    <th>Buy Exchange</th>
                    <th>Buy Price</th>
                    <th>Sell Exchange</th>
                    <th>Sell Price</th>
                    <th>Amount</th>
                    <th>PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTrades.map((trade, index) => (
                    <tr key={index}>
                      <td>{new Date(trade.timestamp).toLocaleString()}</td>
                      <td>{trade.symbol}</td>
                      <td>{trade.buy_exchange}</td>
                      <td>{trade.buy_price?.toFixed(2)}</td>
                      <td>{trade.sell_exchange}</td>
                      <td>{trade.sell_price?.toFixed(2)}</td>
                      <td>{trade.amount}</td>
                      <td className={trade.pnl > 0 ? 'pnl-positive' : trade.pnl < 0 ? 'pnl-negative' : ''}>{trade.pnl?.toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No recent trades.</p>
          )}
        </div>
      </main>
    </div>
  );
}

// Wrap AppContent with QueryClientProvider
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
