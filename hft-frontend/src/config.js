const config = {
  apiUrl: process.env.NODE_ENV === 'production' 
    ? 'https://high-frequency-trading-eu.onrender.com'
    : 'http://localhost:8000',
  wsUrl: process.env.NODE_ENV === 'production'
    ? 'wss://high-frequency-trading-eu.onrender.com'
    : 'ws://localhost:8000',
};

export default config; 