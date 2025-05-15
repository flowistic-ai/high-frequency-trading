import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchLeaderboard } from '../api';

const Leaderboard: React.FC = () => {
  const { data: leaderboard, error, isLoading } = useQuery(
    ['leaderboard'],
    fetchLeaderboard,
    {
      refetchInterval: 5000, // Refresh every 5 seconds
    }
  );

  if (isLoading) return <div className="text-white">Loading leaderboard...</div>;
  if (error) return <div className="text-red-500">Error loading leaderboard: {error.message}</div>;
  if (!leaderboard || leaderboard.length === 0) return <div className="text-white">No leaderboard data available</div>;

  return (
    <div className="bg-gray-800 p-4 rounded-lg">
      <h2 className="text-xl font-bold mb-4 text-white">Trading Performance</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="px-4 py-2 text-left text-white">Symbol</th>
              <th className="px-4 py-2 text-right text-white">PnL</th>
              <th className="px-4 py-2 text-right text-white">Trades</th>
              <th className="px-4 py-2 text-right text-white">Win Rate</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.map((entry, index) => (
              <tr key={index} className="border-b border-gray-700">
                <td className="px-4 py-2 text-white">{entry.symbol}</td>
                <td className={`px-4 py-2 text-right ${entry.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {entry.pnl.toFixed(6)}
                </td>
                <td className="px-4 py-2 text-right text-white">{entry.trades}</td>
                <td className="px-4 py-2 text-right text-white">{(entry.win_rate * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Leaderboard; 