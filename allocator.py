"""
DSE Portfolio Allocator
Reads analyzed stock rankings, picks top N candidates, and distributes
the configured budget equally across them.

Output: output/recommendations.csv
"""

import math
import os
import sys

import pandas as pd

import config


def load_analyzed_data():
    """Load the analyzed and ranked stock data."""
    path = config.RAW_DATA_CSV.replace("raw_stock_data", "analyzed_stocks")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run analyzer.py first.")
        sys.exit(1)

    df = pd.read_csv(path)
    print(f"Loaded {len(df)} ranked stocks from {path}")
    return df


def select_portfolio(df, budget):
    """
    Select stocks with sector-diversified equal-weight allocation.
    Uses config.TARGET_STOCKS and config.MAX_PER_SECTOR for diversity.
    Excludes tickers in config.EXCLUDED_TICKERS.
    """
    target_n = config.TARGET_STOCKS
    max_per_sector = config.MAX_PER_SECTOR

    # Exclude specific tickers
    if config.EXCLUDED_TICKERS:
        excluded = [t.upper() for t in config.EXCLUDED_TICKERS]
        df = df[~df["ticker"].str.upper().isin(excluded)].copy()
        print(f"  Excluded tickers: {', '.join(excluded)}")

    # Sector-diversified selection: walk down ranked list, cap per sector
    sector_counts = {}
    selected_indices = []

    for idx, row in df.iterrows():
        sector = row["sector"]
        if sector_counts.get(sector, 0) >= max_per_sector:
            continue  # Skip — this sector is full
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        selected_indices.append(idx)
        if len(selected_indices) >= target_n:
            break

    portfolio = df.loc[selected_indices].copy()
    per_stock_budget = budget / len(portfolio)

    print(f"\nPortfolio: {len(portfolio)} stocks (max {max_per_sector}/sector)")
    print(f"Budget per stock: BDT {per_stock_budget:,.0f}")
    print(f"Sectors represented: {portfolio['sector'].nunique()}")

    return portfolio, per_stock_budget


def calculate_allocation(portfolio, per_stock_budget):
    """
    Calculate how many shares to buy of each stock.
    DSE uses market lot of 1 (most stocks), so we can buy any quantity.
    """
    portfolio = portfolio.copy()

    # Shares to buy: fees are ON TOP (Net Value = Order Value + Commission)
    # So max shares where (shares × price × 1.0035) ≤ budget
    fee_multiplier = 1 + config.BROKERAGE_FEE_PCT / 100
    portfolio["shares_to_buy"] = (per_stock_budget / (portfolio["ltp"] * fee_multiplier)).apply(math.floor)

    # Order value (what goes to share purchase)
    portfolio["investment_bdt"] = portfolio["shares_to_buy"] * portfolio["ltp"]
    # Commission per stock
    portfolio["commission_bdt"] = (portfolio["investment_bdt"] * config.BROKERAGE_FEE_PCT / 100).round(2)
    # Net deducted from BO account
    portfolio["net_value_bdt"] = portfolio["investment_bdt"] + portfolio["commission_bdt"]

    # Estimated annual dividend yield (dividend_pct is on face_value)
    # Yield = (dividend_pct/100 * face_value) / ltp * 100
    portfolio["dividend_yield_pct"] = (
        portfolio["latest_dividend_pct"].fillna(0) / 100
        * portfolio["face_value"].fillna(10)
        / portfolio["ltp"] * 100
    ).round(2)

    # Estimated annual dividend income per position
    portfolio["est_annual_dividend"] = (
        portfolio["shares_to_buy"]
        * portfolio["face_value"].fillna(10)
        * portfolio["latest_dividend_pct"].fillna(0) / 100
    ).round(0)

    return portfolio


def run():
    """Main allocation pipeline."""
    budget = config.TOTAL_BUDGET_BDT

    print("=" * 60)
    print("DSE PORTFOLIO ALLOCATOR")
    print(f"BO Account balance: BDT {budget:,}")
    print(f"Commission:         {config.BROKERAGE_FEE_PCT}% on top of order value")
    print(f"Strategy:           Equal-weight ({budget // config.TARGET_STOCKS:,.0f} per stock)")
    print("=" * 60)

    df = load_analyzed_data()

    # Select portfolio — full budget divided equally
    portfolio, per_stock_budget = select_portfolio(df, budget)

    # Calculate allocation
    portfolio = calculate_allocation(portfolio, per_stock_budget)

    # Display results
    print("\n" + "=" * 60)
    print("RECOMMENDED PORTFOLIO")
    print("=" * 60)

    display_cols = [
        "ticker", "sector", "ltp", "shares_to_buy", "investment_bdt",
        "commission_bdt", "net_value_bdt",
        "stability_score", "range_pct", "dividend_yield_pct",
        "est_annual_dividend",
    ]
    display = portfolio[display_cols].copy()
    display["stability_score"] = display["stability_score"].round(3)
    display["range_pct"] = display["range_pct"].round(1)
    display["investment_bdt"] = display["investment_bdt"].round(0)

    print(display.to_string(index=False))

    # Summary
    total_order_value = portfolio["investment_bdt"].sum()
    total_commission = portfolio["commission_bdt"].sum()
    total_net = portfolio["net_value_bdt"].sum()
    total_dividend = portfolio["est_annual_dividend"].sum()
    remaining = config.TOTAL_BUDGET_BDT - total_net

    print("\n" + "-" * 60)
    print("SUMMARY")
    print("-" * 60)
    print(f"  BO Account balance:     BDT {config.TOTAL_BUDGET_BDT:>12,.0f}")
    print(f"  Target per stock:       BDT {per_stock_budget:>12,.0f}")
    print(f"  Order value (shares):   BDT {total_order_value:>12,.0f}")
    print(f"  Commission (0.35%):     BDT {total_commission:>12,.2f}")
    print(f"  Net deducted from BO:   BDT {total_net:>12,.2f}")
    print(f"  Remaining in BO:        BDT {remaining:>12,.2f}")
    print(f"  Number of stocks:       {len(portfolio)}")
    print(f"  Est. annual dividends:  BDT {total_dividend:>12,.0f}")
    print(f"  Est. dividend yield:    {total_dividend / total_order_value * 100:.1f}%")
    print(f"  Avg. stability score:   {portfolio['stability_score'].mean():.3f}")
    print(f"  Avg. 52-wk range:       {portfolio['range_pct'].mean():.1f}%")

    # Save to CSV
    os.makedirs("output", exist_ok=True)
    save_cols = [
        "ticker", "sector", "ltp", "shares_to_buy", "investment_bdt",
        "stability_score", "range_pct", "week52_high", "week52_low",
        "pe_ratio", "latest_dividend_pct", "dividend_yield_pct",
        "est_annual_dividend", "market_category", "trade_count",
    ]
    portfolio[save_cols].to_csv(config.RECOMMENDATIONS_CSV, index=False)
    print(f"\n✓ Recommendations saved to {config.RECOMMENDATIONS_CSV}")

    # Risk note
    print("\n⚠️  DISCLAIMER: This is a data-driven screening tool, not financial advice.")
    print("   Past stability does not guarantee future performance.")
    print("   Verify each stock independently before investing.")


if __name__ == "__main__":
    run()
