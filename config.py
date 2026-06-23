"""
Configuration for DSE Stable Stock Screener.
Adjust these parameters to change analysis behavior.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env file if present

# Budget — set your own BO account balance
TOTAL_BUDGET_BDT = int(os.environ.get("DSE_BUDGET_BDT", 100_000))
BROKERAGE_FEE_PCT = 0.35  # Commission on top of order value (Shanta Securities Easy Trade)

# Allocation strategy
ALLOCATION = "equal_weight"  # equal_weight is the only supported strategy

# Sector exclusions (case-insensitive match against DSE sector names)
EXCLUDED_SECTORS = [
    "bank",
    "banking",
]

# Individual stock exclusions (tickers to skip regardless of score)
# Set DSE_EXCLUDED_TICKERS env var as comma-separated list, e.g. "TICK1,TICK2"
_excluded_env = os.environ.get("DSE_EXCLUDED_TICKERS", "")
EXCLUDED_TICKERS = [t.strip() for t in _excluded_env.split(",") if t.strip()]

# Portfolio diversity
TARGET_STOCKS = 10  # Aim for this many positions
MAX_PER_SECTOR = 3  # Cap stocks from any single sector

# Quality filters
MARKET_CATEGORY_WHITELIST = ["A"]  # Only Category A stocks (most regulated)
MAX_PE_RATIO = 40  # Exclude extremely overvalued stocks
MIN_TRADE_COUNT = 50  # Minimum daily trades (liquidity filter)

# Stability scoring weights (must sum to 1.0)
WEIGHT_VOLATILITY = 0.40
WEIGHT_DIVIDEND = 0.30
WEIGHT_LIQUIDITY = 0.20
WEIGHT_PE = 0.10

# Scraping
REQUEST_DELAY_SECONDS = 0.5  # Delay between HTTP requests to DSE
DSE_BASE_URL = "https://www.dsebd.org"

# Output paths
RAW_DATA_CSV = "output/raw_stock_data.csv"
RECOMMENDATIONS_CSV = "output/recommendations.csv"
