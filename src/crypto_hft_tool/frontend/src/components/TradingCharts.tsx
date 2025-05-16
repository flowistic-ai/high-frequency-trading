import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchMarketData } from '../api';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const TradingCharts: React.FC = () => {
  const { data, error, isLoading } = useQuery(
    ['marketData'],
    fetchMarketData,
    {
      refetchInterval: 1000,
    }
  );

  if (isLoading) return <div>Loading charts...</div>;
  if (error) return <div>Error loading chart data: {error.message}</div>;
  if (!data) return <div>No chart data available</div>;

  const commonLayout = {
    height: 600,
    margin: { l: 50, r: 50, t: 50, b: 50 },
    paper_bgcolor: '#1a1a1a',
    plot_bgcolor: '#1a1a1a',
    font: { color: '#ffffff' },
    xaxis: {
      gridcolor: '#333333',
      color: '#ffffff',
      title: 'Time',
    },
    yaxis: {
      gridcolor: '#333333',
      color: '#ffffff',
      title: 'Price (USDT)',
    },
  };

  return (
    <div className="grid grid-cols-1 gap-6">
      {['BTC/USDT', 'ETH/USDT'].map((symbol) => {
        const symbolData = data.data[symbol];
        if (!symbolData) return null;

        return (
          <div key={symbol} className="w-full">
            <Plot
              data={[
                {
                  x: [new Date()],
                  y: [symbolData.mid_price],
                  type: 'scatter',
                  mode: 'lines',
                  name: symbol,
                  line: { color: '#00ff00' },
                },
              ]}
              layout={{
                ...commonLayout,
                title: {
                  text: `${symbol} Price Chart`,
                  font: { color: '#ffffff' },
                },
              }}
              config={{
                displayModeBar: true,
                responsive: true,
              }}
              style={{ width: '100%', height: '600px' }}
            />
          </div>
        );
      })}
    </div>
  );
};

export default TradingCharts; 