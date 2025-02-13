import streamlit as st
import os
import configparser

# -------------------------------
# Function: Load Configurations
# -------------------------------

def load_config():
    """Loads API keys and trading configurations from Streamlit secrets or a local config file."""
    if "API" in st.secrets and "CONFIG" in st.secrets:
        # ✅ Load from Streamlit Secrets (Cloud Deployment)
        settings = {
            "POLYGON_API_KEY": st.secrets["API"]["POLYGON_API_KEY"],
            "CSV_WATCHLIST": st.secrets["CONFIG"]["CSV_WATCHLIST"],
            "START_DATE": st.secrets["CONFIG"]["START_DATE"],
            "END_DATE": st.secrets["CONFIG"]["END_DATE"],
            "INITIAL_CAPITAL": float(st.secrets["CONFIG"]["INITIAL_CAPITAL"]),
            "RISK_PER_TRADE": float(st.secrets["CONFIG"]["RISK_PER_TRADE"])
        }
    else:
        # ✅ Load from Local File (Local Testing)
        config = configparser.ConfigParser()
        config.read(".streamlit/secrets.toml")  # Load local secrets file

        settings = {
            "POLYGON_API_KEY": config.get("API", "POLYGON_API_KEY"),
            "CSV_WATCHLIST": config.get("CONFIG", "CSV_WATCHLIST"),
            "START_DATE": config.get("CONFIG", "START_DATE"),
            "END_DATE": config.get("CONFIG", "END_DATE"),
            "INITIAL_CAPITAL": float(config.get("CONFIG", "INITIAL_CAPITAL")),
            "RISK_PER_TRADE": float(config.get("CONFIG", "RISK_PER_TRADE"))
        }

    return settings

# Load configurations
config = load_config()

# Assign settings to variables
POLYGON_API_KEY = config["POLYGON_API_KEY"]
CSV_WATCHLIST = config["CSV_WATCHLIST"]
START_DATE = config["START_DATE"]
END_DATE = config["END_DATE"]
INITIAL_CAPITAL = config["INITIAL_CAPITAL"]
RISK_PER_TRADE = config["RISK_PER_TRADE"]
