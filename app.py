import os
import time
import requests
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from scipy.stats import percentileofscore

# -------------------------------
# Configuration
# -------------------------------

POLYGON_API_KEY = "YOUR_POLYGON_API_KEY"  # Replace with your API key
CSV_WATCHLIST = "watchlist.csv"  # File containing tickers to scan
START_DATE = "2018-01-01"
END_DATE = "2023-01-01"
INITIAL_CAPITAL = 100000  # Starting capital for backtest
RISK_PER_TRADE = 0.02  # 2% risk per trade

# -------------------------------
# Function: Fetch Historical Data
# -------------------------------

def fetch_polygon_data(ticker, start_date, end_date, timespan="day"):
    """Fetches historical stock data from Polygon.io."""
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/{timespan}/{start_date}/{end_date}?apiKey={POLYGON_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching data for {ticker}: {response.json()}")
        return None
    data = response.json().get("results", [])
    if not data:
        return None
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    return df[["date", "Open", "High", "Low", "Close", "Volume"]]

# -------------------------------
# Function: Fetch SPY Market Breadth Data
# -------------------------------

def fetch_spy_market_condition(start_date, end_date):
    """Fetches SPY market data to check if it's in a bullish or bearish trend."""
    spy_data = fetch_polygon_data("SPY", start_date, end_date)
    if spy_data is None or len(spy_data) < 50:
        return "Unknown"  # If data is missing, return "Unknown"

    # Calculate 50-day Moving Average
    spy_data["50SMA"] = spy_data["Close"].rolling(50).mean()

    # Determine if SPY is in a bullish or bearish condition
    if spy_data["Close"].iloc[-1] > spy_data["50SMA"].iloc[-1]:
        return "Bullish ✅"
    else:
        return "Bearish ❌"

# -------------------------------
# Function: Scanner for Ultra-Low Volatility
# -------------------------------

def scan_stocks(tickers):
    """Scans stocks for ultra-low volatility and breakout setups."""
    valid_stocks = []
    
    for ticker in tickers:
        df = fetch_polygon_data(ticker, START_DATE, END_DATE)
        if df is None or len(df) < 50:
            continue  # Skip if insufficient data

        # Compute Bollinger Band Width (BBW) & ATR
        df["BBW"] = (df["High"].rolling(20).max() - df["Low"].rolling(20).min()) / df["Close"]
        df["ATR"] = df["High"].rolling(14).max() - df["Low"].rolling(14).min()
        df["AvgVol"] = df["Volume"].rolling(50).mean()

        # Compute thresholds for BBW & ATR (10th percentile)
        bbw_threshold = np.percentile(df["BBW"].dropna(), 10)
        atr_threshold = np.percentile(df["ATR"].dropna(), 10)

        # Require volume expansion on breakout day (1.5x the 50-day avg)
        volume_condition = df["Volume"].iloc[-1] > 1.5 * df["AvgVol"].iloc[-1]

        if df["BBW"].iloc[-1] < bbw_threshold and df["ATR"].iloc[-1] < atr_threshold and volume_condition:
            valid_stocks.append(ticker)

    return valid_stocks

# -------------------------------
# Function: Entry & Improved Stop-Loss Logic
# -------------------------------

def calculate_trade_parameters(df):
    """Calculates entry price, stop-loss, and profit target with improved logic."""
    high_range = df["High"].rolling(20).max().iloc[-1]
    low_range = df["Low"].rolling(20).min().iloc[-1]
    atr = df["ATR"].iloc[-1]

    entry_price = high_range * 0.98  # Slightly below breakout point
    stop_loss = max(low_range - (atr * 1.5), df["Low"].rolling(5).min().iloc[-1])  # Improved stop-loss logic
    risk_per_share = entry_price - stop_loss
    target_price = entry_price + (2 * risk_per_share)

    return entry_price, stop_loss, target_price

# -------------------------------
# Backtest Function
# -------------------------------

def backtest(tickers):
    """Runs backtest on selected tickers."""
    capital = INITIAL_CAPITAL
    trade_log = []
    
    for ticker in tickers:
        df = fetch_polygon_data(ticker, START_DATE, END_DATE)
        if df is None or len(df) < 50:
            continue

        entry_price, stop_loss, target_price = calculate_trade_parameters(df)

        for i in range(len(df) - 1):
            if df["High"].iloc[i] >= entry_price:
                shares = (capital * RISK_PER_TRADE) // (entry_price - stop_loss)
                entry_date = df["date"].iloc[i]
                stop_hit = df["Low"].iloc[i+1] <= stop_loss
                target_hit = df["High"].iloc[i+1] >= target_price

                exit_date = df["date"].iloc[i+3] if not (stop_hit or target_hit) else (
                    df["date"].iloc[i+1] if stop_hit else df["date"].iloc[i+1]
                )
                exit_price = stop_loss if stop_hit else target_price if target_hit else df["Close"].iloc[i+3]
                pnl = (exit_price - entry_price) * shares

                trade_log.append([ticker, entry_date, exit_date, entry_price, exit_price, pnl])
                capital += pnl
    
    trade_df = pd.DataFrame(trade_log, columns=["Ticker", "Entry Date", "Exit Date", "Entry Price", "Exit Price", "PnL"])
    return trade_df, capital

# -------------------------------
# Streamlit UI
# -------------------------------

st.title("Swing Trading Scanner & Backtester")

# Display Market Breadth Indicator
market_condition = fetch_spy_market_condition(START_DATE, END_DATE)
st.header(f"Market Breadth: {market_condition}")

# Load Watchlist
if os.path.exists(CSV_WATCHLIST):
    watchlist = pd.read_csv(CSV_WATCHLIST)["Symbol"].tolist()
    st.write(f"Loaded {len(watchlist)} tickers.")
else:
    st.error("Watchlist CSV not found.")
    watchlist = []

# Scan Stocks
if st.button("Run Scanner"):
    with st.spinner("Scanning stocks..."):
        candidates = scan_stocks(watchlist)
        st.success(f"Found {len(candidates)} candidates.")
        st.write(candidates)

# Backtest Candidates
if st.button("Run Backtest"):
    with st.spinner("Running backtest..."):
        trade_df, final_capital = backtest(candidates)
        st.write(f"Final Capital: ${final_capital:,.2f}")
        st.dataframe(trade_df)

        # Plot Equity Curve
        trade_df["Cumulative PnL"] = trade_df["PnL"].cumsum()
        plt.figure(figsize=(10, 5))
        plt.plot(trade_df["Entry Date"], trade_df["Cumulative PnL"], label="Equity Curve")
        plt.xlabel("Date")
        plt.ylabel("Cumulative PnL ($)")
        plt.title("Backtest Equity Curve")
        plt.legend()
        st.pyplot(plt)
