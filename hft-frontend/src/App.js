import React, { useState, useEffect, useCallback } from 'react';
import Plot from 'react-plotly.js'; // Import Plotly component
import './App.css';

// const API_BASE_URL = 'http://127.0.0.1:8000'; // Your FastAPI backend URL
const API_BASE_URL = 'https://high-frequency-trading-frankfurt.onrender.com'; // <-- REPLACE WITH YOUR ACTUAL NEW RENDER URL
const SYMBOLS = [
  "BTC/USDT", "ETH/USDT", "LTC/USDT", "XRP/USDT", "BCH/USDT", "ADA/USDT", "SOL/USDT", "DOGE/USDT", "DOT/USDT", "LINK/USDT"
];
const REFRESH_INTERVAL = 2000; // Milliseconds (e.g., 2 seconds)
const MAX_HISTORY_POINTS = 300; // Number of data points to keep for charts

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState(SYMBOLS[0]);
  const [marketData, setMarketData] = useState(null);
  const [simulationStatus, setSimulationStatus] = useState(null);
  const [recentTrades, setRecentTrades] = useState([]);
  const [sentimentData, setSentimentData] = useState(null);
  const [history, setHistory] = useState({
    timestamp: [],
    spread: [],
    z_score: [],
    binance_ask: [],
    kraken_bid: [],
  });
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [leaderboard, setLeaderboard] = useState([]);
  const [allMarketData, setAllMarketData] = useState({});

  const fetchData = useCallback(async () => {
    try {
      const [marketRes, simStatusRes, tradesRes, sentimentRes, leaderboardRes, allMarketRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/v1/market_data/${encodeURIComponent(selectedSymbol)}`),
        fetch(`${API_BASE_URL}/api/v1/simulation/status`),
        fetch(`${API_BASE_URL}/api/v1/simulation/trades?limit=10`),
        fetch(`${API_BASE_URL}/api/v1/sentiment/${encodeURIComponent(selectedSymbol)}`),
        fetch(`${API_BASE_URL}/api/v1/simulation/leaderboard`),
        fetch(`${API_BASE_URL}/api/v1/market_data/all`),
      ]);

      if (!marketRes.ok) throw new Error(`Market Data API Error: ${marketRes.status}`);
      if (!simStatusRes.ok) throw new Error(`Simulation Status API Error: ${simStatusRes.status}`);
      if (!tradesRes.ok) throw new Error(`Trades API Error: ${tradesRes.status}`);
      if (!sentimentRes.ok) throw new Error(`Sentiment API Error: ${sentimentRes.status}`);
      if (!leaderboardRes.ok) throw new Error(`Leaderboard API Error: ${leaderboardRes.status}`);
      if (!allMarketRes.ok) throw new Error(`All Market Data API Error: ${allMarketRes.status}`);

      const marketDataJson = await marketRes.json();
      const simStatusJson = await simStatusRes.json();
      const tradesJson = await tradesRes.json();
      const sentimentJson = await sentimentRes.json();
      const leaderboardJson = await leaderboardRes.json();
      const allMarketJson = await allMarketRes.json();

      setMarketData(marketDataJson);
      setSimulationStatus(simStatusJson);
      setRecentTrades(tradesJson.trades || []);
      setSentimentData(sentimentJson);
      setLeaderboard(leaderboardJson.leaderboard || []);
      setAllMarketData(allMarketJson.data || {});

      if (marketDataJson && !marketDataJson.error) {
        setHistory(prevHistory => {
          const newTimestamp = [...prevHistory.timestamp, new Date(marketDataJson.timestamp)];
          const newSpread = [...prevHistory.spread, marketDataJson.spread];
          const newZScore = [...prevHistory.z_score, marketDataJson.z_score];
          const newBinanceAsk = [...prevHistory.binance_ask, marketDataJson.binance?.ask];
          const newKrakenBid = [...prevHistory.kraken_bid, marketDataJson.kraken?.bid];
          const trim = (arr) => arr.slice(Math.max(0, arr.length - MAX_HISTORY_POINTS));
          return {
            timestamp: trim(newTimestamp),
            spread: trim(newSpread),
            z_score: trim(newZScore),
            binance_ask: trim(newBinanceAsk),
            kraken_bid: trim(newKrakenBid),
          };
        });
      }
      else if (marketDataJson.error) {
        console.warn("DataProvider error:", marketDataJson.error);
      }
      setError(null);
    } catch (err) {
      console.error("Failed to fetch data:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    setHistory({ timestamp: [], spread: [], z_score: [], binance_ask: [], kraken_bid: [] }); // Reset history on symbol change
    fetchData();
    const intervalId = setInterval(fetchData, REFRESH_INTERVAL);
    return () => clearInterval(intervalId);
  }, [fetchData, selectedSymbol]);

  // Define Plotly layout (can be customized further)
  const commonLayout = {
    autosize: true,
    margin: { l: 60, r: 40, t: 60, b: 50 }, // Adjusted margins
    paper_bgcolor: '#1e1e1e', // Dark background for plot area (Kept as per user "apart from graphs")
    plot_bgcolor: '#1e1e1e',
    font: { color: '#ffffff' }, // White font for graph text (Kept as per user)
    xaxis: { gridcolor: '#444', color: '#ffffff' }, // Dark grid lines, white ticks
    yaxis: { gridcolor: '#444', color: '#ffffff' }, // Dark grid lines, white ticks
    legend: { orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "right", x: 1, font: { color: '#ffffff' } }
  };

  // --- Live Trades Ticker ---
  const tradesTicker = (
    <div className="live-trades-ticker">
      <h2>Live Trades</h2>
      <div className="ticker-content" style={{ overflowX: 'auto', whiteSpace: 'nowrap', border: '1px solid #ccc', padding: '5px' }}>
        {recentTrades.length > 0 ? (
          recentTrades.map((trade, index) => (
            <span key={index} style={{ marginRight: '20px' }}>
              {trade.symbol} {trade.buy_exchange} &gt; {trade.sell_exchange} @ {trade.sell_price.toFixed(4)} (PnL: {trade.pnl.toFixed(6)})
            </span>
          ))
        ) : (
          <span>No live trades yet...</span>
        )}
      </div>
    </div>
  );

  // --- Leaderboard Table ---
  const leaderboardTable = (
    <div className="leaderboard-section">
      <h2>Leaderboard</h2>
      {leaderboard.length === 0 || leaderboard.every(entry => entry.trade_count === 0) ? (
        <div className="no-trades-message">No trades yet.</div>
      ) : (
        <table className="leaderboard-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Total PnL</th>
              <th>Trade Count</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.map((entry, idx) => (
              <tr key={entry.symbol} className={entry.symbol === selectedSymbol ? 'selected-symbol-row' : ''}>
                <td>{entry.symbol}</td>
                <td className={entry.total_pnl > 0 ? 'pnl-positive' : entry.total_pnl < 0 ? 'pnl-negative' : ''}>{entry.total_pnl.toFixed(6)}</td>
                <td>{entry.trade_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  // --- Z-Score Heatmap ---
  const zScoreHeatmap = (
    <div className="zscore-heatmap-section">
      <h2>Z-Score Heatmap</h2>
      <div className="zscore-heatmap-legend">
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#ff6666'}}></span> | Z &gt; 2.0 (Strong Positive)</div>
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#ffe066'}}></span> | 1.2 &lt; Z ≤ 2.0 (Moderate)</div>
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#b2f7ef'}}></span> | -1.2 ≤ Z ≤ 1.2 (Neutral)</div>
        <div className="zscore-legend-box"><span className="zscore-legend-color" style={{background:'#66b3ff'}}></span> | Z &lt; -1.2 (Strong Negative)</div>
      </div>
      <div className="zscore-heatmap-grid">
        {SYMBOLS.map(sym => {
          const z = allMarketData[sym]?.z_score;
          let bg = '#b2f7ef';
          if (typeof z === 'number') {
            if (z > 2) bg = '#ff6666'; // strong positive
            else if (z > 1.2) bg = '#ffe066'; // moderate
            else if (z < -1.2) bg = '#66b3ff'; // strong negative
            else bg = '#b2f7ef'; // neutral
          }
          return (
            <div
              key={sym}
              className="zscore-heatmap-cell"
              style={{ background: bg, color: '#222', border: sym === selectedSymbol ? '2px solid #0197ae' : '1px solid #ccc' }}
              onClick={() => setSelectedSymbol(sym)}
            >
              <div style={{ fontSize: 13 }}>{sym}</div>
              <div style={{ fontSize: 18 }}>{typeof z === 'number' ? z.toFixed(2) : 'N/A'}</div>
              <div className="zscore-tooltip">Z-score: {typeof z === 'number' ? z.toFixed(4) : 'N/A'}<br/>Click to view {sym}</div>
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="App">
      <header className="App-header">
        <div className="App-logo-container">
          {/* Use process.env.PUBLIC_URL for items in the public folder */} 
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
          {isLoading && <p>Loading initial data...</p>}
          {error && <p className="error-message">Error: {error}</p>}
          {!isLoading && !error && marketData && !marketData.error && <p className="status-ok">Live Data Feed Running</p>}
          {marketData?.error && <p className="error-message">Provider Error: {marketData.error}</p>}

          <div className="metrics-container">
              {simulationStatus ? (
                <>
                  <div className="metric-item"><span>Total PnL:</span> {simulationStatus.total_pnl?.toFixed(6)}</div>
                  <div className="metric-item"><span>Total Trades:</span> {simulationStatus.total_trades}</div>
                </>
              ) : <div className="metric-item">Loading status...</div> }
              
              {simulationStatus ? (
                <>
                  <div className="metric-item strategy-param"><span>Z-Threshold:</span> {simulationStatus.z_score_threshold?.toFixed(1)}</div>
                  <div className="metric-item strategy-param"><span>Trade Amount:</span> {simulationStatus.trade_amount}</div>
                  <div className="metric-item strategy-param"><span>Exit Z:</span> {simulationStatus.exit_z_threshold?.toFixed(1)}</div>
                  <div className="metric-item strategy-param"><span>Stop Loss:</span> {simulationStatus.stop_loss_amount?.toFixed(2)}</div>
                </>
              ) : <div className="metric-item">Loading params...</div>}
              
              {sentimentData ? (
                 <>
                   <div className="metric-item"><span>Sentiment:</span> {sentimentData.sentiment_label} ({sentimentData.sentiment_score?.toFixed(2)})</div>
                 </>
              ) : <div className="metric-item">Loading sentiment...</div>}
          </div>
        </div>

        <div className="chart-section chart-section-prices">
          {history.timestamp.length > 0 ? (
            <Plot
              data={[
                { x: history.timestamp, y: history.binance_ask, type: 'scatter', mode: 'lines', name: 'Binance Ask', yaxis: 'y1', line: { color: '#ff6666', dash: 'dot' }, hoverinfo: 'x+y' },
                { x: history.timestamp, y: history.kraken_bid, type: 'scatter', mode: 'lines', name: 'Kraken Bid', yaxis: 'y1', line: { color: '#66b3ff', dash: 'dot' }, hoverinfo: 'x+y' },
                { x: history.timestamp, y: history.spread, type: 'scatter', mode: 'lines', name: 'Spread', yaxis: 'y2', line: { color: '#66ff66' }, hoverinfo: 'x+y' },
              ]}
              layout={{
                ...commonLayout,
                title: 'Market Prices & Spread',
                hovermode: 'x unified',
                yaxis: { title: 'Price (USDT)', side: 'left', gridcolor: '#444', color: '#ffffff', titlefont: { color: '#ffffff' } },
                yaxis2: { title: 'Spread (USDT)', overlaying: 'y', side: 'right', showgrid: false, zeroline: false, color: '#66ff66', titlefont: { color: '#66ff66' } },
              }}
              style={{ width: '100%', height: '100%' }}
              useResizeHandler={true}
            />
          ) : <p>Waiting for price/spread data...</p>}
        </div>

        <div className="chart-section chart-section-zscore">
          {history.timestamp.length > 0 ? (
            <Plot
              data={[
                { x: history.timestamp, y: history.z_score, type: 'scatter', mode: 'lines', name: 'Z-Score', line: { color: '#cc99ff' }, hoverinfo: 'x+y' },
              ]}
              layout={{
                ...commonLayout,
                title: 'Spread Z-Score',
                hovermode: 'x unified',
                yaxis: { title: 'Z-Score', zeroline: true, zerolinecolor: '#888', gridcolor: '#444', color: '#ffffff', titlefont: { color: '#ffffff' } },
                shapes: [
                  { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: simulationStatus?.z_score_threshold || 2.0, y1: simulationStatus?.z_score_threshold || 2.0, line: { color: 'orange', width: 1, dash: 'dash' }, name: 'Upper Threshold' },
                  { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: -(simulationStatus?.z_score_threshold || 2.0), y1: -(simulationStatus?.z_score_threshold || 2.0), line: { color: 'orange', width: 1, dash: 'dash' }, name: 'Lower Threshold' },
                  { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: simulationStatus?.exit_z_threshold || 0.5, y1: simulationStatus?.exit_z_threshold || 0.5, line: { color: 'cyan', width: 1, dash: 'dot' }, name: 'Exit Threshold' },
                  { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: -(simulationStatus?.exit_z_threshold || 0.5), y1: -(simulationStatus?.exit_z_threshold || 0.5), line: { color: 'cyan', width: 1, dash: 'dot' }, name: 'Exit Threshold' }
                ]
              }}
              style={{ width: '100%', height: '100%' }}
              useResizeHandler={true}
            />
          ) : <p>Waiting for Z-score data...</p>}
        </div>

        <div className="trades-section">
          <h2>Recent Trades</h2>
          {recentTrades.length > 0 ? (
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

export default App;
