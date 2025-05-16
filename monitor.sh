#!/bin/bash

# Kill any existing processes on ports 3000 and 8000
echo "Cleaning up existing processes..."
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Start backend server with logging
echo "Starting backend server..."
cd /Users/syedzeewaqarhussain/crypto_hft_tool
source venv/bin/activate
uvicorn src.crypto_hft_tool.main:app --reload --port 8000 --log-level debug > backend.log 2>&1 &
BACKEND_PID=$!

# Start frontend server with logging
echo "Starting frontend server..."
cd /Users/syedzeewaqarhussain/crypto_hft_tool/hft-frontend
npm start > frontend.log 2>&1 &
FRONTEND_PID=$!

# Function to check server health
check_health() {
    echo "Checking server health..."
    
    # Check backend
    if curl -s http://localhost:8000/api/v1/market_data/all > /dev/null; then
        echo "✅ Backend is responding"
    else
        echo "❌ Backend is not responding"
    fi
    
    # Check frontend
    if curl -s http://localhost:3000 > /dev/null; then
        echo "✅ Frontend is responding"
    else
        echo "❌ Frontend is not responding"
    fi
}

# Monitor logs
echo "Monitoring logs (Ctrl+C to stop)..."
tail -f backend.log frontend.log &

# Check health every 5 seconds
while true; do
    check_health
    sleep 5
done

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM 