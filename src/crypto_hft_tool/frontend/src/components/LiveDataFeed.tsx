import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchMarketData } from '../api';

const LiveDataFeed: React.FC = () => {
  const { data, error, isLoading } = useQuery(
    ['marketData'],
    fetchMarketData,
    {
      refetchInterval: 1000, // Refresh every second
    }
  );

  if (isLoading) return <div>Loading market data...</div>;
  if (error) return <div>Error loading market data: {error.message}</div>;
  if (!data) return <div>No market data available</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {Object.entries(data.data).map(([symbol, symbolData]: [string, any]) => (
        <div key={symbol} className="bg-gray-800 p-4 rounded-lg">
          <h3 className="text-lg font-semibold mb-2 text-white">{symbol}</h3>
          <div className="grid grid-cols-2 gap-2">
            <div className="text-sm text-gray-300">Bid: <span className="text-white">${symbolData.bid?.toFixed(2)}</span></div>
            <div className="text-sm text-gray-300">Ask: <span className="text-white">${symbolData.ask?.toFixed(2)}</span></div>
            <div className="text-sm text-gray-300">Mid: <span className="text-white">${symbolData.mid_price?.toFixed(2)}</span></div>
            <div className="text-sm text-gray-300">Volume: <span className="text-white">{symbolData.baseVolume?.toFixed(2)}</span></div>
            <div className="text-sm text-gray-300">Z-Score: <span className="text-white">{symbolData.z_score?.toFixed(2)}</span></div>
            <div className="text-sm text-gray-300">Signal: <span className={`text-${symbolData.signal > 0 ? 'green' : symbolData.signal < 0 ? 'red' : 'gray'}-400`}>
              {symbolData.signal?.toFixed(2)}
            </span></div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default LiveDataFeed; 