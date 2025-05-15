import React from 'react';
import { useQuery } from 'react-query';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  CircularProgress
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from 'recharts';
import api from '../services/api';

const Dashboard: React.FC = () => {
  const { data: marketData, isLoading: marketLoading } = useQuery(
    'marketData',
    api.getAllMarketData,
    { refetchInterval: 1000 }
  );

  const { data: simulationStatus, isLoading: statusLoading } = useQuery(
    'simulationStatus',
    api.getSimulationStatus,
    { refetchInterval: 1000 }
  );

  const { data: recentTrades, isLoading: tradesLoading } = useQuery(
    'recentTrades',
    () => api.getRecentTrades(10),
    { refetchInterval: 1000 }
  );

  if (marketLoading || statusLoading || tradesLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl">
      <Box my={4}>
        <Typography variant="h4" gutterBottom>
          Crypto HFT Dashboard
        </Typography>

        <Grid container spacing={3}>
          {/* Performance Metrics */}
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6">Performance</Typography>
              <Typography variant="h4">
                ${simulationStatus?.total_pnl.toFixed(2)}
              </Typography>
              <Typography color="textSecondary">
                Total Trades: {simulationStatus?.total_trades}
              </Typography>
            </Paper>
          </Grid>

          {/* Market Data */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Market Data
              </Typography>
              <Grid container spacing={2}>
                {Object.entries(marketData?.data || {}).map(([symbol, data]: [string, any]) => (
                  <Grid item xs={12} md={4} key={symbol}>
                    <Paper sx={{ p: 2 }}>
                      <Typography variant="h6">{symbol}</Typography>
                      <Typography>
                        Spread: ${data.spread.toFixed(6)}
                      </Typography>
                      <Typography>
                        Z-Score: {data.z_score?.toFixed(2) || 'N/A'}
                      </Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>

          {/* Recent Trades */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Recent Trades
              </Typography>
              <Box sx={{ overflowX: 'auto' }}>
                {recentTrades?.trades.map((trade: any, index: number) => (
                  <Box key={index} sx={{ mb: 1 }}>
                    <Typography>
                      {trade.symbol} - PnL: ${trade.pnl.toFixed(2)}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      {new Date(trade.timestamp).toLocaleString()}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
};

export default Dashboard; 