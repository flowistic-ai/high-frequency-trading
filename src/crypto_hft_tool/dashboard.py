import os
import streamlit as st
import pandas as pd
# import time # Not explicitly used if relying on autorefresh and no manual sleeps
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go # Import Plotly
from plotly.subplots import make_subplots # For multiple y-axes if needed later

from crypto_hft_tool.config import SYMBOLS # Ensure config.py has SYMBOLS and data_folder
from crypto_hft_tool.signals import RollingZScore
from crypto_hft_tool.simulation import TradeSimulator
from crypto_hft_tool.risk_manager import RiskManager
from crypto_hft_tool.data_provider import DataProvider

load_dotenv() 

st.set_page_config(layout="wide") # Use wider layout

# --- Helper to re-initialize state for a new symbol/setting --- 
def initialize_modules(window_size_val):
    st.session_state.ztracker = RollingZScore(window_size=window_size_val)
    st.session_state.sim = TradeSimulator() # Reset simulation PnL etc.
    st.session_state.risk = RiskManager()   # Reset risk states
    st.session_state.history = {'timestamp': [], 'spread': [], 'z': [], 'binance_ask': [], 'kraken_bid': []} # Clear history
    st.session_state.trades = [] # Clear trades

# --- Sidebar Controls --- 
st.sidebar.header("Settings")

# Initialize session state for controls if they don't exist to prevent errors on first run
if 'symbol_select_tracker' not in st.session_state: st.session_state.symbol_select_tracker = SYMBOLS[0] if SYMBOLS else "BTC/USDT"
if 'window_size_tracker' not in st.session_state: st.session_state.window_size_tracker = 200
if 'z_thresh_tracker' not in st.session_state: st.session_state.z_thresh_tracker = 2.0

selected_symbol = st.sidebar.selectbox("Symbol", SYMBOLS, 
                                     index=SYMBOLS.index(st.session_state.symbol_select_tracker) if st.session_state.symbol_select_tracker in SYMBOLS else 0,
                                     key="symbol_selector")
new_window_size = st.sidebar.slider("Z-score Window", min_value=10, max_value=1000, 
                                   value=st.session_state.window_size_tracker, 
                                   step=10, key="window_slider_ctrl")
new_z_thresh = st.sidebar.slider("Z-score Threshold", min_value=0.5, max_value=5.0, 
                                value=st.session_state.z_thresh_tracker, 
                                step=0.1, key="z_thresh_slider_ctrl")
trade_amt = st.sidebar.number_input("Trade Amount", value=0.001, min_value=0.000001, step=0.0001, format="%.6f")

# Update trackers and re-initialize if settings changed
if st.session_state.symbol_select_tracker != selected_symbol:
    st.session_state.symbol_select_tracker = selected_symbol
    initialize_modules(new_window_size) # Reset for new symbol

if st.session_state.window_size_tracker != new_window_size:
    st.session_state.window_size_tracker = new_window_size
    initialize_modules(new_window_size) # Re-initialize with new window

st.session_state.z_thresh_tracker = new_z_thresh # z_thresh can be updated live

start_live_button = st.sidebar.button("Start Live Data")
stop_live_button = st.sidebar.button("Stop Live Data")

# --- Session State Setup (Core Components) ---
if "live" not in st.session_state: st.session_state.live = False
if "provider" not in st.session_state: 
    st.session_state.provider = DataProvider(live=False) # Default to backtest/inactive
    if st.session_state.provider.error: 
        st.sidebar.error(f"Provider Init (backtest mode): {st.session_state.provider.error}")

if "ztracker" not in st.session_state: # Ensure all modules are initialized at least once
    initialize_modules(st.session_state.window_size_tracker)

# --- Handle Start/Stop Actions --- 
if start_live_button:
    st.session_state.live = True
    st.session_state.provider = DataProvider(live=True) # Switch to live provider
    initialize_modules(st.session_state.window_size_tracker) # Reset history for fresh live run
    if st.session_state.provider.error: 
        st.sidebar.error(f"Provider Start (live mode): {st.session_state.provider.error}")
    st.rerun() # Rerun to reflect state change immediately

if stop_live_button:
    st.session_state.live = False
    # Optionally, switch provider back to non-live. For now, just stopping is fine.
    # st.session_state.provider = DataProvider(live=False)
    st.rerun() # Rerun to reflect state change

# --- Autorefresh when live ---
if st.session_state.live:
    st_autorefresh(interval=1000, limit=None, key='refresh_counter') # limit=None for indefinite refresh

# --- UI Placeholders --- 
st.title(f"Crypto Arbitrage Dashboard ({st.session_state.symbol_select_tracker})")
status_box = st.empty()
error_box = st.empty() 

# Main chart area for spread and underlying prices
price_spread_chart_placeholder = st.empty()
# Separate chart area for Z-score
z_chart_placeholder = st.empty()

metrics_placeholder = st.empty()
trades_table_placeholder = st.empty()
pnl_metric_placeholder = st.empty()

# --- Main Data Fetching and Processing Logic --- 
if st.session_state.live:
    status_box.success(f"Live data feed running. Refresh count: {st.session_state.get('refresh_counter', 0)}")
    
    books = st.session_state.provider.get_top_of_book(st.session_state.symbol_select_tracker)

    if st.session_state.provider.error:
        error_box.error(f"Data Fetch Error: {st.session_state.provider.error}")
    elif books:
        error_box.empty() # Clear previous error if data is now fine
        bid_bin, ask_bin = books['binance']['bid'], books['binance']['ask']
        bid_kr, ask_kr   = books['kraken']['bid'],  books['kraken']['ask']

        spread = ask_bin - bid_kr 
        z = st.session_state.ztracker.add(spread)
        ts = pd.Timestamp.utcnow()

        st.session_state.history['timestamp'].append(ts)
        st.session_state.history['spread'].append(spread)
        st.session_state.history['z'].append(z)
        st.session_state.history['binance_ask'].append(ask_bin) # Store for combined chart
        st.session_state.history['kraken_bid'].append(bid_kr)   # Store for combined chart

        if len(st.session_state.history['timestamp']) > 300: # Keep history to last 300 points for performance
            for k_hist in ['timestamp','spread','z', 'binance_ask', 'kraken_bid']:
                st.session_state.history[k_hist] = st.session_state.history[k_hist][-300:]
        
        current_z_thresh = st.session_state.z_thresh_tracker
        if abs(z) >= current_z_thresh:
            if st.session_state.risk.can_trade(st.session_state.symbol_select_tracker, trade_amt):
                pnl_val = 0.0
                if z > 0: # Spread is high (Binance ask > Kraken bid), so sell Binance, buy Kraken
                    pnl_val = st.session_state.sim.simulate_trade(
                        st.session_state.symbol_select_tracker, 'kraken', ask_kr, 'binance', bid_bin, trade_amt
                    )
                else: # Spread is low (Binance ask < Kraken bid), so buy Binance, sell Kraken
                    pnl_val = st.session_state.sim.simulate_trade(
                        st.session_state.symbol_select_tracker, 'binance', ask_bin, 'kraken', bid_kr, trade_amt
                    )
                st.session_state.risk.register_trade(trade_amt, pnl_val)
                st.session_state.trades.append({
                    'timestamp': ts, 
                    'symbol': st.session_state.symbol_select_tracker,
                    'spread': round(spread, 4), 
                    'z': round(z, 2), 
                    'pnl': round(pnl_val, 6)
                })
    # else: if books is None but no provider.error, it might be end of backtest data.

else: # Not live
    status_box.warning("Live data feed stopped. Configure settings and click 'Start Live Data' to begin.")
    error_box.empty() # Clear any previous live errors
    if st.session_state.provider and st.session_state.provider.error: # Show init/backtest errors if any
        error_box.warning(f"Provider Status (Offline): {st.session_state.provider.error}")

# --- UI Rendering with Plotly --- 
df_history = pd.DataFrame(st.session_state.history)
if not df_history.empty:
    df_history = df_history.set_index('timestamp')

    # Create Plotly figure for Spread and Underlying Prices
    fig_spread = make_subplots(specs=[[{"secondary_y": True}]])
    fig_spread.add_trace(
        go.Scatter(x=df_history.index, y=df_history['binance_ask'], name="Binance Ask", line=dict(color='red', dash='dot')),
        secondary_y=False,
    )
    fig_spread.add_trace(
        go.Scatter(x=df_history.index, y=df_history['kraken_bid'], name="Kraken Bid", line=dict(color='blue', dash='dot')),
        secondary_y=False,
    )
    fig_spread.add_trace(
        go.Scatter(x=df_history.index, y=df_history['spread'], name="Spread (Ask_Bin - Bid_Kr)", line=dict(color='green')),
        secondary_y=True,
    )
    fig_spread.update_layout(
        title_text="Market Prices and Spread",
        xaxis_title="Timestamp",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_spread.update_yaxes(title_text="Price (e.g., USDT)", secondary_y=False)
    fig_spread.update_yaxes(title_text="Spread", secondary_y=True, showgrid=False)
    price_spread_chart_placeholder.plotly_chart(fig_spread, use_container_width=True)

    # Create Plotly figure for Z-score
    fig_z = go.Figure()
    fig_z.add_trace(go.Scatter(x=df_history.index, y=df_history['z'], name="Z-score", line=dict(color='purple')))
    # Add threshold lines for Z-score
    z_thresh_val = st.session_state.z_thresh_tracker
    fig_z.add_hline(y=z_thresh_val, line_dash="dash", line_color="orange", annotation_text=f"Upper Threshold ({z_thresh_val})")
    fig_z.add_hline(y=-z_thresh_val, line_dash="dash", line_color="orange", annotation_text=f"Lower Threshold ({-z_thresh_val})")
    fig_z.update_layout(
        title_text="Spread Z-score",
        xaxis_title="Timestamp", yaxis_title="Z-score",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    z_chart_placeholder.plotly_chart(fig_z, use_container_width=True)
else:
    price_spread_chart_placeholder.info("History is empty. Start live data to see charts.")
    z_chart_placeholder.info("History is empty.")

# Trades Table
df_trades = pd.DataFrame(st.session_state.trades)
if not df_trades.empty:
    trades_table_placeholder.subheader("Recent Trades")
    trades_table_placeholder.table(df_trades.tail(10).sort_index(ascending=False)) # Show last 10, newest first
else:
    trades_table_placeholder.info("No trades simulated yet.")

# PnL Metric
pnl_metric_placeholder.metric("Cumulative PnL", f"{st.session_state.sim.total_pnl:.6f}")

# Other metrics
if not df_trades.empty:
    win_count = len(df_trades[df_trades['pnl'] > 0])
    loss_count = len(df_trades[df_trades['pnl'] < 0])
    total_trades_val = len(df_trades)
    win_rate = (win_count / total_trades_val * 100) if total_trades_val > 0 else 0
    avg_pnl = df_trades['pnl'].mean() if total_trades_val > 0 else 0
    
    m_cols = metrics_placeholder.columns(4)
    m_cols[0].metric("Total Trades", total_trades_val)
    m_cols[1].metric("Win Rate", f"{win_rate:.2f}%")
    m_cols[2].metric("Avg PnL/Trade", f"{avg_pnl:.6f}")
    m_cols[3].metric("Wins / Losses", f"{win_count} / {loss_count}")
else:
    metrics_placeholder.info("Trade metrics will appear here once trades are simulated.")
