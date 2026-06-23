"""
DSE Stock Stability Analyzer
Reads raw_stock_data.csv, scores each stock for stability, and outputs ranked results.

Scoring:
  - Volatility (40%): Lower 52-week range percentage = better
  - Dividend (30%): More years of dividends + higher recent pct = better
  - Liquidity (20%): Higher trade count = better (can exit easily)
  - P/E ratio (10%): Moderate P/E preferred over extremes

Output: Prints ranked table + saves filtered candidates for allocator.py
"""

import os
import sys

import pandas as pd

import config


def load_data():
    """Load the raw stock data CSV."""
    if not os.path.exists(config.RAW_DATA_CSV):
        print(f"ERROR: {config.RAW_DATA_CSV} not found. Run scraper.py first.")
        sys.exit(1)

    df = pd.read_csv(config.RAW_DATA_CSV)
    print(f"Loaded {len(df)} stocks from {config.RAW_DATA_CSV}")
    return df


def apply_quality_filters(df):
    """Apply hard filters to remove unsuitable stocks."""
    initial_count = len(df)

    # Filter 1: Must have a valid LTP (currently trading)
    df = df[df["ltp"].notna() & (df["ltp"] > 0)].copy()
    print(f"  After LTP filter: {len(df)} stocks")

    # Filter 2: Must have 52-week range data
    df = df[df["week52_high"].notna() & df["week52_low"].notna()].copy()
    print(f"  After 52-week range filter: {len(df)} stocks")

    # Filter 3: Market Category A only
    if config.MARKET_CATEGORY_WHITELIST:
        df = df[df["market_category"].isin(config.MARKET_CATEGORY_WHITELIST)].copy()
        print(f"  After Category A filter: {len(df)} stocks")

    # Filter 4: P/E ratio sanity (if available, exclude extreme values)
    # Don't exclude stocks without P/E — just penalize them in scoring
    if config.MAX_PE_RATIO:
        df = df[(df["pe_ratio"].isna()) | (df["pe_ratio"] <= config.MAX_PE_RATIO)].copy()
        print(f"  After P/E filter (≤{config.MAX_PE_RATIO}): {len(df)} stocks")

    # Filter 5: Minimum trading activity (liquidity)
    df = df[df["trade_count"].notna() & (df["trade_count"] >= config.MIN_TRADE_COUNT)].copy()
    print(f"  After liquidity filter (≥{config.MIN_TRADE_COUNT} trades): {len(df)} stocks")

    # Filter 6: Exclude stocks where 52-week low is 0 or near-zero (suspicious)
    df = df[df["week52_low"] > 1].copy()

    print(f"\n  Filtered: {initial_count} → {len(df)} stocks")
    return df


def calculate_volatility_score(df):
    """
    Volatility score based on 52-week range.
    Range% = (high - low) / midpoint * 100
    Lower range = more stable = higher score.
    """
    midpoint = (df["week52_high"] + df["week52_low"]) / 2
    range_pct = (df["week52_high"] - df["week52_low"]) / midpoint * 100

    df["range_pct"] = range_pct

    # Normalize: lower range_pct = higher score (0 to 1)
    # Use min-max normalization inverted
    min_range = range_pct.min()
    max_range = range_pct.max()

    if max_range == min_range:
        df["volatility_score"] = 0.5
    else:
        df["volatility_score"] = 1 - (range_pct - min_range) / (max_range - min_range)

    return df


def calculate_dividend_score(df):
    """
    Dividend score based on:
    - Whether the stock pays dividends at all
    - How many consecutive/recent years of dividends
    - Latest dividend percentage relative to face value
    """
    # Normalize dividend years (0 to 1) — more years = better
    max_years = df["dividend_years"].max()
    if max_years and max_years > 0:
        years_score = df["dividend_years"].fillna(0) / max_years
    else:
        years_score = 0

    # Normalize latest dividend pct
    max_div = df["latest_dividend_pct"].max()
    if max_div and max_div > 0:
        div_pct_score = df["latest_dividend_pct"].fillna(0) / max_div
    else:
        div_pct_score = 0

    # Combine: 60% weight on years (consistency), 40% on recent pct (magnitude)
    df["dividend_score"] = 0.6 * years_score + 0.4 * div_pct_score

    return df


def calculate_liquidity_score(df):
    """
    Liquidity score based on daily trade count.
    More trades = easier to buy/sell = higher score.
    """
    trade_count = df["trade_count"].fillna(0)
    max_trades = trade_count.max()

    if max_trades > 0:
        # Use log scale since trade counts vary enormously
        import numpy as np
        log_trades = np.log1p(trade_count)
        max_log = log_trades.max()
        df["liquidity_score"] = log_trades / max_log if max_log > 0 else 0
    else:
        df["liquidity_score"] = 0

    return df


def calculate_pe_score(df):
    """
    P/E score: moderate P/E (8-20) is preferred.
    Too low might mean trouble, too high means overvalued.
    """
    pe = df["pe_ratio"].copy()

    # Stocks without P/E get a neutral score
    df["pe_score"] = 0.5

    # Ideal P/E range: 8-20 gets the highest score
    has_pe = pe.notna()
    ideal_mask = has_pe & (pe >= 8) & (pe <= 20)
    moderate_mask = has_pe & ((pe >= 5) & (pe < 8) | (pe > 20) & (pe <= 30))
    extreme_mask = has_pe & ((pe < 5) | (pe > 30))

    df.loc[ideal_mask, "pe_score"] = 1.0
    df.loc[moderate_mask, "pe_score"] = 0.6
    df.loc[extreme_mask, "pe_score"] = 0.2

    return df


def calculate_composite_score(df):
    """Compute weighted composite stability score."""
    df["stability_score"] = (
        config.WEIGHT_VOLATILITY * df["volatility_score"]
        + config.WEIGHT_DIVIDEND * df["dividend_score"]
        + config.WEIGHT_LIQUIDITY * df["liquidity_score"]
        + config.WEIGHT_PE * df["pe_score"]
    )
    return df


def run():
    """Main analysis pipeline."""
    print("=" * 60)
    print("DSE STOCK STABILITY ANALYZER")
    print("=" * 60)

    # Load data
    df = load_data()

    # Apply quality filters
    print("\nApplying quality filters...")
    df = apply_quality_filters(df)

    if df.empty:
        print("\nNo stocks passed all filters. Check your data or relax filters in config.py.")
        sys.exit(1)

    # Calculate individual scores
    print("\nCalculating stability scores...")
    df = calculate_volatility_score(df)
    df = calculate_dividend_score(df)
    df = calculate_liquidity_score(df)
    df = calculate_pe_score(df)
    df = calculate_composite_score(df)

    # Sort by composite score
    df = df.sort_values("stability_score", ascending=False).reset_index(drop=True)

    # Display top results
    print("\n" + "=" * 60)
    print("TOP 20 MOST STABLE STOCKS (excluding banking)")
    print("=" * 60)

    display_cols = [
        "ticker", "sector", "ltp", "range_pct", "pe_ratio",
        "latest_dividend_pct", "dividend_years", "trade_count",
        "stability_score",
    ]
    top20 = df.head(20)[display_cols].copy()
    top20["range_pct"] = top20["range_pct"].round(1)
    top20["stability_score"] = top20["stability_score"].round(3)

    print(top20.to_string(index=False))

    # Save full ranked results
    output_path = config.RAW_DATA_CSV.replace("raw_stock_data", "analyzed_stocks")
    df.to_csv(output_path, index=False)
    print(f"\n✓ Full ranked results saved to {output_path}")
    print(f"  Total qualifying stocks: {len(df)}")

    # Summary stats
    print("\n--- Score Distribution ---")
    print(f"  Top score:    {df['stability_score'].max():.3f}")
    print(f"  Median score: {df['stability_score'].median():.3f}")
    print(f"  Bottom score: {df['stability_score'].min():.3f}")
    print(f"  Mean range%:  {df['range_pct'].mean():.1f}%")


if __name__ == "__main__":
    run()
