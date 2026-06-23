"""
Unit tests for the DSE Portfolio Allocator.
Tests fee calculation, share allocation, and sector diversification.
"""

import math

import pandas as pd
import pytest

import config
from allocator import calculate_allocation, select_portfolio


def make_analyzed_df(overrides=None, n=15):
    """Create a synthetic analyzed DataFrame (pre-scored, sorted)."""
    sectors = ["Pharma", "Cement", "Telecom", "Fuel", "Food",
               "Pharma", "Cement", "Telecom", "Fuel", "Food",
               "Pharma", "Cement", "Telecom", "Fuel", "Food"][:n]
    base = {
        "ticker": [f"STOCK{i}" for i in range(n)],
        "sector": sectors,
        "ltp": [100.0] * n,
        "stability_score": [1.0 - i * 0.05 for i in range(n)],
        "week52_high": [120.0] * n,
        "week52_low": [80.0] * n,
        "pe_ratio": [15.0] * n,
        "latest_dividend_pct": [20.0] * n,
        "dividend_years": [5] * n,
        "face_value": [10.0] * n,
        "trade_count": [200] * n,
        "range_pct": [40.0] * n,
        "market_category": ["A"] * n,
    }
    df = pd.DataFrame(base)
    if overrides:
        for col, values in overrides.items():
            df[col] = values
    return df


# --- Fee Calculation ---


class TestFeeCalculation:
    def test_fee_on_top_of_order(self):
        """Commission is ON TOP: Net = Order + Commission."""
        df = make_analyzed_df(n=1)
        df["ltp"] = [1000.0]
        portfolio, per_stock = select_portfolio(df, 100_000)
        result = calculate_allocation(portfolio, per_stock)

        row = result.iloc[0]
        shares = row["shares_to_buy"]
        order_value = shares * 1000.0
        commission = order_value * config.BROKERAGE_FEE_PCT / 100

        assert row["investment_bdt"] == order_value
        assert abs(row["commission_bdt"] - commission) < 0.01
        assert abs(row["net_value_bdt"] - (order_value + commission)) < 0.01

    def test_shares_respect_fee_budget(self):
        """shares * price * (1 + fee%) must be <= budget per stock."""
        df = make_analyzed_df(n=1)
        df["ltp"] = [500.0]
        budget = 50_000
        portfolio, per_stock = select_portfolio(df, budget)
        result = calculate_allocation(portfolio, per_stock)

        row = result.iloc[0]
        net_value = row["net_value_bdt"]
        assert net_value <= per_stock

    def test_shares_floor_not_round(self):
        """Must use floor — never buy fractional or rounded-up shares."""
        df = make_analyzed_df(n=1)
        df["ltp"] = [333.33]
        budget = 33_300
        portfolio, per_stock = select_portfolio(df, budget)
        result = calculate_allocation(portfolio, per_stock)

        fee_multiplier = 1 + config.BROKERAGE_FEE_PCT / 100
        expected_shares = math.floor(per_stock / (333.33 * fee_multiplier))
        assert result.iloc[0]["shares_to_buy"] == expected_shares

    def test_fee_rate_matches_config(self):
        """Commission rate should be exactly config.BROKERAGE_FEE_PCT."""
        df = make_analyzed_df(n=1)
        df["ltp"] = [100.0]
        portfolio, per_stock = select_portfolio(df, 100_000)
        result = calculate_allocation(portfolio, per_stock)

        row = result.iloc[0]
        actual_rate = row["commission_bdt"] / row["investment_bdt"] * 100
        assert abs(actual_rate - config.BROKERAGE_FEE_PCT) < 0.001


# --- Portfolio Selection ---


class TestPortfolioSelection:
    def test_selects_target_stocks(self):
        """Should select exactly config.TARGET_STOCKS positions."""
        df = make_analyzed_df(n=15)
        portfolio, _ = select_portfolio(df, 100_000)
        assert len(portfolio) == config.TARGET_STOCKS

    def test_sector_cap_enforced(self):
        """No sector should exceed config.MAX_PER_SECTOR."""
        df = make_analyzed_df({"sector": ["Pharma"] * 15})
        portfolio, _ = select_portfolio(df, 100_000)
        sector_counts = portfolio["sector"].value_counts()
        assert sector_counts.max() <= config.MAX_PER_SECTOR

    def test_sector_cap_picks_from_others(self):
        """When a sector is capped, should move to next-ranked stock from another sector."""
        sectors = ["Pharma", "Pharma", "Pharma", "Pharma",  # 4 pharma — only 3 allowed
                   "Cement", "Cement", "Cement",
                   "Telecom", "Telecom", "Telecom",
                   "Fuel", "Food", "IT", "Energy", "Misc"]
        df = make_analyzed_df({"sector": sectors}, n=15)
        portfolio, _ = select_portfolio(df, 100_000)
        pharma_count = (portfolio["sector"] == "Pharma").sum()
        assert pharma_count <= config.MAX_PER_SECTOR

    def test_excluded_tickers_removed(self, monkeypatch):
        """Tickers in config.EXCLUDED_TICKERS should not appear in portfolio."""
        monkeypatch.setattr(config, "EXCLUDED_TICKERS", ["BADSTOCK"])
        df = make_analyzed_df(n=15)
        df.loc[0, "ticker"] = "BADSTOCK"
        portfolio, _ = select_portfolio(df, 100_000)
        assert "BADSTOCK" not in portfolio["ticker"].values

    def test_excluded_tickers_case_insensitive(self, monkeypatch):
        """Exclusion should work regardless of case."""
        monkeypatch.setattr(config, "EXCLUDED_TICKERS", ["BADSTOCK"])
        df = make_analyzed_df(n=15)
        df.loc[0, "ticker"] = "badstock"
        portfolio, _ = select_portfolio(df, 100_000)
        assert "badstock" not in portfolio["ticker"].values

    def test_selection_order_respects_rank(self):
        """Higher-ranked stocks should be selected first (within sector cap)."""
        df = make_analyzed_df(n=15)
        portfolio, _ = select_portfolio(df, 100_000)
        # First selected should be the highest-scoring
        assert portfolio.iloc[0]["ticker"] == "STOCK0"

    def test_equal_budget_split(self):
        """Per-stock budget should be total / number of positions."""
        df = make_analyzed_df(n=15)
        portfolio, per_stock = select_portfolio(df, 100_000)
        expected = 100_000 / len(portfolio)
        assert abs(per_stock - expected) < 0.01


# --- Allocation Math ---


class TestAllocationMath:
    def test_investment_equals_shares_times_price(self):
        df = make_analyzed_df(n=1)
        df["ltp"] = [250.0]
        portfolio, per_stock = select_portfolio(df, 50_000)
        result = calculate_allocation(portfolio, per_stock)
        row = result.iloc[0]
        assert row["investment_bdt"] == row["shares_to_buy"] * 250.0

    def test_net_value_is_investment_plus_commission(self):
        df = make_analyzed_df(n=1)
        df["ltp"] = [150.0]
        portfolio, per_stock = select_portfolio(df, 50_000)
        result = calculate_allocation(portfolio, per_stock)
        row = result.iloc[0]
        assert abs(row["net_value_bdt"] - (row["investment_bdt"] + row["commission_bdt"])) < 0.01

    def test_total_net_within_budget(self):
        """Sum of all net values must not exceed total budget."""
        df = make_analyzed_df(n=15)
        df["ltp"] = [100 + i * 50 for i in range(15)]
        portfolio, per_stock = select_portfolio(df, 100_000)
        result = calculate_allocation(portfolio, per_stock)
        total_net = result["net_value_bdt"].sum()
        assert total_net <= 100_000

    def test_dividend_yield_calculation(self):
        """dividend_yield_pct = (div_pct/100 * face_value) / ltp * 100."""
        df = make_analyzed_df(n=1)
        df["ltp"] = [200.0]
        df["latest_dividend_pct"] = [30.0]
        df["face_value"] = [10.0]
        portfolio, per_stock = select_portfolio(df, 50_000)
        result = calculate_allocation(portfolio, per_stock)
        # Expected: (30/100 * 10) / 200 * 100 = 1.5%
        assert abs(result.iloc[0]["dividend_yield_pct"] - 1.5) < 0.01

    def test_high_price_stock_gets_fewer_shares(self):
        df = make_analyzed_df(n=2)
        df["ltp"] = [3000.0, 50.0]
        df["sector"] = ["Pharma", "Cement"]
        portfolio, per_stock = select_portfolio(df, 66_000)
        result = calculate_allocation(portfolio, per_stock)
        assert result.iloc[0]["shares_to_buy"] < result.iloc[1]["shares_to_buy"]
