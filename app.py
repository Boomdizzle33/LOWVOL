import os
import time
import requests
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from scipy.stats import percentileofscore
import configparser

# -------------------------------
# Function: Load Configurations
# -------------------------------

def load_config():
    """Loads API keys and trading configurations from Streamlit secrets or a local file."""
    if "API" in st.secrets and "CONFIG" in st.secrets:
        # ✅ Load from Streamlit Secrets (Cloud Deployment)
        settings = {
            "POLYGON_API_KEY": st.secrets["API"]["POLYGON_API_KEY"],
            "START_DATE": st.secrets["CONFIG"]["START_DATE"],
            "END_DATE": st.secrets["CONFIG"]["END_DATE"],
            "INITIAL_CAPITAL": float(st.secrets["CONFIG"]["INITIAL_CAPITAL"]),
            "RISK_PER_TRADE": float(st.secrets["CONFIG"]["RISK_PER_TRADE"])
        }
    else:
        # ✅ Load from Local Config File
        config = configparser.ConfigParser()
        config.read(".streamlit/secrets.toml")
        settings = {
            "POLYGON_API_KEY": config.get("API", "POLYGON_API_KEY"),
            "START_DATE": config.get("CONFIG", "START_DATE"),
            "END_DATE": config.get("CONFIG", "END_DATE"),
            "INITIAL_CAPITAL": float(config.get("CONFIG", "INITIAL_CAPITAL")),
            "RISK_PER_TRADE": float(config.get("CONFIG", "RISK_PER_TRADE"))
        }
    
    return settings

# Load Configurations
config = load_config()
POLYGON_API_KEY = config["POLYGON_API_KEY"]
START_DATE = config["START_DATE"]
END_DATE = config["END_DATE"]
INITIAL_CAPITAL = config["INITIAL_CAPITAL"]
RISK_PER_TRADE = config["RISK_PER_TRADE"]

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
        return "Unknown"

    spy_data["50SMA"] = spy_data["Close"].rolling(50).mean()
    return "Bullish ✅" if spy_data["Close"].iloc[-1] > spy_data["50SMA"].iloc[-1] else "Bearish ❌"

# -------------------------------
# Function: Scanner for Ultra-Low Volatility
# -------------------------------

def scan_stocks(tickers):
    """Scans stocks for ultra-low volatility and breakout setups."""
    valid_stocks = []
    
    for ticker in tickers:
        df = fetch_polygon_data(ticker, START_DATE, END_DATE)
        if df is None or len(df) < 50:
            continue

        df["BBW"] = (df["High"].rolling(20).max() - df["Low"].rolling(20).min()) / df["Close"]
        df["ATR"] = df["High"].rolling(14).max() - df["Low"].rolling(14).min()
        df["AvgVol"] = df["Volume"].rolling(50).mean()

        bbw_threshold = np.percentile(df["BBW"].dropna(), 10)
        atr_threshold = np.percentile(df["ATR"].dropna(), 10)
        volume_condition = df["Volume"].iloc[-1] > 1.5 * df["AvgVol"].iloc[-1]

        if df["BBW"].iloc[-1] < bbw_threshold and df["ATR"].iloc[-1] < atr_threshold and volume_condition:
            valid_stocks.append(ticker)

    return valid_stocks

# -------------------------------
# Function: Entry & Stop-Loss Logic
# -------------------------------

def calculate_trade_parameters(df):
    """Calculates entry price, stop-loss, and profit target with ATR-based logic."""
    high_range = df["High"].rolling(20).max().iloc[-1]
    low_range = df["Low"].rolling(20).min().iloc[-1]
    atr = df["ATR"].iloc[-1]

    entry_price = high_range * 0.98
    stop_loss = max(low_range - (atr * 1.5), df["Low"].rolling(5).min().iloc[-1])
    risk_per_share = entry_price - stop_loss
    target_price = entry_price + (2 * risk_per_share)

    return entry_price, stop_loss, target_price

# -------------------------------
# Streamlit UI
# -------------------------------

st.title("Swing Trading Scanner & Backtester")

# Display Market Breadth Indicator
market_condition = fetch_spy_market_condition(START_DATE, END_DATE)
st.header(f"Market Breadth: {market_condition}")

# Upload TradingView Watchlist (Ticker Column Required)
uploaded_file = st.file_uploader("Upload TradingView Watchlist CSV", type="csv")
if uploaded_file:
    df_watchlist = pd.read_csv(uploaded_file)
    if "Ticker" in df_watchlist.columns:
        watchlist = df_watchlist["Ticker"].tolist()
        st.success(f"Imported {len(watchlist)} tickers from TradingView.")
    else:
        st.error("Invalid CSV format. Ensure the column is named 'Ticker'.")
        watchlist = []
else:
    watchlist = []

# Scan Stocks
if st.button("Run Scanner"):
    if watchlist:
        with st.spinner("Scanning stocks..."):
            candidates = scan_stocks(watchlist)
            if candidates:
                st.success(f"Found {len(candidates)} candidates.")
                st.write(candidates)
            else:
                st.warning("No stocks matched the screening criteria.")
    else:
        st.error("Please upload a TradingView watchlist file before scanning.")

# Run Backtest
if st.button("Run Backtest"):
    if not watchlist:
        st.error("No stocks available for backtesting. Please run the scanner first.")
    else:
        with st.spinner("Running backtest..."):
            trade_df, final_capital = backtest(watchlist)
            st.write(f"Final Capital: ${final_capital:,.2f}")
            st.dataframe(trade_df)

            trade_df["Cumulative PnL"] = trade_df["PnL"].cumsum()
            plt.figure(figsize=(10, 5))
            plt.plot(trade_df["Entry Date"], trade_df["Cumulative PnL"], label="Equity Curve")
            plt.xlabel("Date")
            plt.ylabel("Cumulative PnL ($)")
            plt.title("Backtest Equity Curve")
            plt.legend()
            st.pyplot(plt)

