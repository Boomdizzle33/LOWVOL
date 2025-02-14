import pandas as pd
import numpy as np
import requests
import streamlit as st
import json
import os

# Retrieve API Key from Streamlit Secrets
if "POLYGON_API_KEY" in st.secrets:
    API_KEY = st.secrets["POLYGON_API_KEY"]
else:
    st.error("Polygon API Key is missing. Please add it to Streamlit secrets via the Streamlit Cloud UI.")
    API_KEY = None

BASE_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?apiKey=" + API_KEY

# Fetch Historical Data from Polygon.io
def fetch_stock_data(ticker, start_date, end_date):
    if API_KEY is None:
        return None
    print(f"Fetching data for {ticker} from {start_date} to {end_date}")
    url = BASE_URL.format(ticker=ticker, start_date=start_date, end_date=end_date)
    response = requests.get(url)
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Fetched {len(data['results'])} records for {ticker}")
        return pd.DataFrame(data["results"])
    else:
        print(f"Error fetching data for {ticker}: {response.json()}")
    return None

# Calculate RMV (Relative Measured Volatility)
def calculate_rmv(data, window=20):
    data["hl_range"] = data["h"] - data["l"]
    data["rmv"] = data["hl_range"].rolling(window=window).mean()
    return data

# Identify Volatility Contraction and Breakout
def detect_trade_signals(data):
    data["volatility_contraction"] = (data["rmv"] < data["rmv"].shift(1)) & (data["rmv"].shift(1) < data["rmv"].shift(2))
    data["resistance"] = data["h"].rolling(window=5).max()
    data["pre_breakout"] = (data["c"] >= data["resistance"] * 0.98) & (data["c"] < data["resistance"]) & data["volatility_contraction"]
    data["breakout"] = (data["c"] > data["resistance"]) & data["volatility_contraction"]
    return data

# Risk Management & Position Sizing
def calculate_trade_parameters(entry_price, stop_loss, risk_per_trade=0.01, account_size=100000):
    risk_amount = account_size * risk_per_trade
    position_size = risk_amount / (entry_price - stop_loss)
    target_price = entry_price + 2 * (entry_price - stop_loss)
    return position_size, target_price

# Backtesting Function
def backtest_strategy(stock_list, start_date, end_date, account_size):
    results = []
    st.subheader("🔍 Scanning Stocks...")
    progress_bar = st.progress(0)
total_stocks = len(stock_list)
    for idx, stock in enumerate(stock_list):
        data = fetch_stock_data(stock, start_date, end_date)
        if data is not None:
            data = calculate_rmv(data)
            data = detect_trade_signals(data)
            for i in range(2, len(data)):
                if data.iloc[i]["breakout"]:
                    entry_price = data.iloc[i]["c"]
                    stop_loss = entry_price - data.iloc[i]["rmv"]
                    position_size, target_price = calculate_trade_parameters(entry_price, stop_loss, account_size=account_size)
                    exit_price = target_price if data.iloc[i+1]["h"] >= target_price else (stop_loss if data.iloc[i+1]["l"] <= stop_loss else data.iloc[i+1]["c"])
                    profit = (exit_price - entry_price) * position_size
                    results.append({"Stock": stock, "Entry": entry_price, "Exit": exit_price, "Profit": profit})
        return pd.DataFrame(results)

# Streamlit UI
def display_dashboard(stock_signals, account_size):
    st.set_page_config(page_title="RMV Swing Trading Scanner", layout="wide")
    st.title("📈 RMV-Based Swing Trading Scanner")
    st.markdown("---")
        for stock, data in stock_signals.items():
        st.subheader(stock)
        entry_price = data.iloc[-1]["c"]
        stop_loss = entry_price - (data.iloc[-1]["rmv"])
        position_size, target_price = calculate_trade_parameters(entry_price, stop_loss, account_size=account_size)
        st.write(f"Entry Price: {entry_price:.2f}, Stop Loss: {stop_loss:.2f}, Target: {target_price:.2f}")

# Main Execution
def main():
    st.title("RMV-Based Swing Trading Scanner")
    account_size = st.number_input("Enter Account Size", min_value=1000, max_value=1000000, value=100000, step=1000)
    uploaded_file = st.file_uploader("Upload TradingView CSV", type=["csv"])
    
    if uploaded_file is not None:
        stock_list = pd.read_csv(uploaded_file)["Ticker"].tolist()
    else:
        stock_list = []
    
    stock_signals = {}
    for stock in stock_list:
        data = fetch_stock_data(stock, "2024-01-01", "2025-02-12")
        progress_bar.progress((idx + 1) / total_stocks)
        print(f"Processing data for {stock}")
        if data is not None:
            data = calculate_rmv(data)
            data = detect_trade_signals(data)
            print(f"Breakout detected for {stock}")
            if data["breakout"].iloc[-1]:
                stock_signals[stock] = data
    
    display_dashboard(stock_signals, account_size)
    progress_bar.empty()
    st.markdown("---")
    st.subheader("📊 Backtesting Results")
        backtest_results = backtest_strategy(stock_list, "2024-01-01", "2025-02-12", account_size)
    st.dataframe(backtest_results)

if __name__ == "__main__":
    main()
