import LiveDataFeed from '@/components/LiveDataFeed';
import TradingSignals from '@/components/TradingSignals';
import RecentTrades from '@/components/RecentTrades';
import Leaderboard from '@/components/Leaderboard';
import TradingCharts from '@/components/TradingCharts';

const Dashboard = () => {
  return (
    <div className="container mx-auto p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <LiveDataFeed />
        <TradingSignals />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <RecentTrades />
        <Leaderboard />
      </div>
      <div className="grid grid-cols-1 gap-4">
        <TradingCharts />
      </div>
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
              </>
            ) : <div className="metric-item">Loading PnL status...</div> }
            
            {simulationStatus ? (
              <>
                <div className="metric-item strategy-param"><span>Z-Threshold:</span> {simulationStatus.z_score_threshold?.toFixed(1)}</div>
                <div className="metric-item strategy-param"><span>Trade Amount:</span> {simulationStatus.trade_amount}</div>
                <div className="metric-item strategy-param"><span>Exit Z:</span> {simulationStatus.exit_z_threshold?.toFixed(1)}</div>
                <div className="metric-item strategy-param"><span>Stop Loss:</span> {simulationStatus.stop_loss_amount?.toFixed(2)}</div>
              </>
            ) : <div className="metric-item">Loading strategy params...</div>}
        </div>
      </div>

      <div className="chart-section chart-section-prices">
      </div>
    </div>
  );
};

export default Dashboard; 