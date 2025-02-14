import pandas as pd
import numpy as np
import requests
import streamlit as st
import json

# Polygon.io API Key
API_KEY = "YOUR_POLYGON_API_KEY"
BASE_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?apiKey=" + API_KEY

# Load TradingView Exported Stock List
def load_stock_list(file_path):
    if file_path.endswith(".csv"):
        return pd.read_csv(file_path)["symbol"].tolist()
    elif file_path.endswith(".json"):
        with open(file_path, "r") as f:
            return json.load(f)["symbols"]
    return []

# Fetch Historical Data from Polygon.io
def fetch_stock_data(ticker, start_date, end_date):
    print(f"Fetching data for {ticker} from {start_date} to {end_date}")
    url = BASE_URL.format(ticker=ticker, start_date=start_date, end_date=end_date)
    response = requests.get(url)
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Fetched {len(data['results'])} records for {ticker}")
        return pd.DataFrame(data["results"])
    return None

# Calculate RMV (Relative Measured Volatility)
def calculate_rmv(data, window=20):
    data["hl_range"] = data["h"] - data["l"]
    data["rmv"] = data["hl_range"].rolling(window=window).mean()
    return data

# Identify Volatility Contraction and Breakout
def detect_trade_signals(data):
    # Identify tight volatility contraction (pre-breakout condition)
    data["volatility_contraction"] = (data["rmv"] < data["rmv"].shift(1)) & (data["rmv"].shift(1) < data["rmv"].shift(2))
    
    # Identify resistance level (previous highs within the last 5 days)
    data["resistance"] = data["h"].rolling(window=5).max()
    
    # Pre-breakout entry condition: price near resistance but not yet breaking out
    data["pre_breakout"] = (data["c"] >= data["resistance"] * 0.98) & (data["c"] < data["resistance"]) & data["volatility_contraction"]
    
    # Standard breakout condition
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
    for stock in stock_list:
        data = fetch_stock_data(stock, start_date, end_date)
        if data is not None:
            data = calculate_rmv(data)
            data = detect_trade_signals(data)
            for i in range(2, len(data)):
                if data.iloc[i]["breakout"]:
                    entry_price = data.iloc[i]["c"]
                    stop_loss = entry_price - data.iloc[i]["rmv"]
                    position_size, target_price = calculate_trade_parameters(entry_price, stop_loss, account_size=account_size)
                    
                    # Simulate exit
                    exit_price = target_price if data.iloc[i+1]["h"] >= target_price else (stop_loss if data.iloc[i+1]["l"] <= stop_loss else data.iloc[i+1]["c"])
                    profit = (exit_price - entry_price) * position_size
                    results.append({"Stock": stock, "Entry": entry_price, "Exit": exit_price, "Profit": profit})
    return pd.DataFrame(results)

# Streamlit UI
def display_dashboard(stock_signals, account_size):
    st.title("RMV-Based Swing Trading Scanner")
    for stock, data in stock_signals.items():
        st.subheader(stock)
        entry_price = data.iloc[-1]["c"]
        stop_loss = entry_price - (data.iloc[-1]["rmv"])
        position_size, target_price = calculate_trade_parameters(entry_price, stop_loss, account_size=account_size)
        st.write(f"Entry Price: {entry_price:.2f}, Stop Loss: {stop_loss:.2f}, Target: {target_price:.2f}")

# Main Execution
def main():
    account_size = st.number_input("Enter Account Size", min_value=1000, max_value=1000000, value=100000, step=1000)
    stock_list = load_stock_list("tradingview_export.csv")
    stock_signals = {}
    
    for stock in stock_list:
        data = fetch_stock_data(stock, "2024-01-01", "2025-02-12")
        print(f"Processing data for {stock}")
        if data is not None:
            data = calculate_rmv(data)
            data = detect_trade_signals(data)
            print(f"Breakout detected for {stock}")
            if data["breakout"].iloc[-1]:  # Check if latest candle is a breakout
                stock_signals[stock] = data
    
    display_dashboard(stock_signals, account_size)
    
    # Run Backtest
    st.subheader("Backtesting Results")
    backtest_results = backtest_strategy(stock_list, "2024-01-01", "2025-02-12", account_size)
    st.dataframe(backtest_results)

if __name__ == "__main__":
    main()


