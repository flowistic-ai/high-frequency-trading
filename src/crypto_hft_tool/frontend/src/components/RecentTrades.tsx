import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchRecentTrades } from '../api';

const RecentTrades: React.FC = () => {
  const { data: trades, error, isLoading } = useQuery(
    ['recentTrades'],
    fetchRecentTrades,
    {
      refetchInterval: 1000,
    }
  );

  if (isLoading) return <div className="text-white">Loading recent trades...</div>;
  if (error) return <div className="text-red-500">Error loading trades: {error.message}</div>;
  if (!trades || trades.length === 0) return <div className="text-white">No recent trades</div>;

  return (
    <div className="bg-gray-800 p-4 rounded-lg">
      <h2 className="text-xl font-bold mb-4 text-white">Recent Trades</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="px-4 py-2 text-left text-white">Time</th>
              <th className="px-4 py-2 text-left text-white">Symbol</th>
              <th className="px-4 py-2 text-right text-white">Price</th>
              <th className="px-4 py-2 text-right text-white">Size</th>
              <th className="px-4 py-2 text-right text-white">Side</th>
              <th className="px-4 py-2 text-right text-white">PnL</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade, index) => (
              <tr key={index} className="border-b border-gray-700">
                <td className="px-4 py-2 text-white">
                  {new Date(trade.timestamp).toLocaleTimeString()}
                </td>
                <td className="px-4 py-2 text-white">{trade.symbol}</td>
                <td className="px-4 py-2 text-right text-white">${trade.price.toFixed(2)}</td>
                <td className="px-4 py-2 text-right text-white">{trade.size.toFixed(6)}</td>
                <td className={`px-4 py-2 text-right ${trade.side === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
                  {trade.side.toUpperCase()}
                </td>
                <td className={`px-4 py-2 text-right ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {trade.pnl.toFixed(6)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RecentTrades; 