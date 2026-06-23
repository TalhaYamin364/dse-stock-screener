"""
Unit tests for the DSE Stock Stability Analyzer.
Tests scoring functions with synthetic data — no network calls.
"""

import pandas as pd
import pytest

import config
from analyzer import (
    apply_quality_filters,
    calculate_composite_score,
    calculate_dividend_score,
    calculate_liquidity_score,
    calculate_pe_score,
    calculate_volatility_score,
)


def make_stock_df(overrides=None, n=5):
    """Create a synthetic stock DataFrame for testing."""
    base = {
        "ticker": [f"STOCK{i}" for i in range(n)],
        "sector": ["Pharma"] * n,
        "ltp": [100.0] * n,
        "week52_high": [120.0] * n,
        "week52_low": [80.0] * n,
        "market_category": ["A"] * n,
        "pe_ratio": [15.0] * n,
        "latest_dividend_pct": [20.0] * n,
        "dividend_years": [5] * n,
        "face_value": [10.0] * n,
        "trade_count": [200] * n,
        "volume": [50000] * n,
    }
    df = pd.DataFrame(base)
    if overrides:
        for col, values in overrides.items():
            df[col] = values
    return df


# --- Quality Filters ---


class TestQualityFilters:
    def test_removes_zero_ltp(self):
        df = make_stock_df({"ltp": [0, 100, 100, 100, 100]})
        result = apply_quality_filters(df)
        assert len(result) == 4

    def test_removes_null_ltp(self):
        df = make_stock_df({"ltp": [None, 100, 100, 100, 100]})
        result = apply_quality_filters(df)
        assert len(result) == 4

    def test_removes_missing_52wk_range(self):
        df = make_stock_df({"week52_high": [None, 120, 120, 120, 120]})
        result = apply_quality_filters(df)
        assert len(result) == 4

    def test_removes_non_category_a(self):
        df = make_stock_df({"market_category": ["B", "A", "A", "A", "Z"]})
        result = apply_quality_filters(df)
        assert len(result) == 3

    def test_removes_high_pe(self):
        df = make_stock_df({"pe_ratio": [50, 15, 15, 15, 15]})
        result = apply_quality_filters(df)
        assert len(result) == 4

    def test_keeps_null_pe(self):
        """Stocks without P/E should NOT be filtered out."""
        df = make_stock_df({"pe_ratio": [None, 15, None, 15, 15]})
        result = apply_quality_filters(df)
        assert len(result) == 5

    def test_removes_low_trade_count(self):
        df = make_stock_df({"trade_count": [10, 200, 200, 200, 200]})
        result = apply_quality_filters(df)
        assert len(result) == 4

    def test_removes_zero_week52_low(self):
        """Suspicious data — 52wk low of 0 or 1 should be excluded."""
        df = make_stock_df({"week52_low": [0.5, 80, 80, 80, 80]})
        result = apply_quality_filters(df)
        assert len(result) == 4

    def test_all_pass(self):
        """Normal data should all pass."""
        df = make_stock_df()
        result = apply_quality_filters(df)
        assert len(result) == 5


# --- Volatility Score ---


class TestVolatilityScore:
    def test_lower_range_gets_higher_score(self):
        """Stock with tighter 52-week range should score higher."""
        df = make_stock_df({
            "week52_high": [110, 150, 120, 120, 120],  # stock0: tight range
            "week52_low": [90, 50, 80, 80, 80],         # stock1: wide range
        })
        result = calculate_volatility_score(df)
        # stock0 range = 20/100 = 20%, stock1 range = 100/100 = 100%
        assert result.iloc[0]["volatility_score"] > result.iloc[1]["volatility_score"]

    def test_identical_ranges_get_equal_score(self):
        """All same range should get 0.5 score."""
        df = make_stock_df()  # all same: 120-80
        result = calculate_volatility_score(df)
        assert (result["volatility_score"] == 0.5).all()

    def test_range_pct_calculated(self):
        """range_pct should be (high-low)/midpoint * 100."""
        df = make_stock_df({
            "week52_high": [120.0, 120, 120, 120, 120],
            "week52_low": [80.0, 80, 80, 80, 80],
        })
        result = calculate_volatility_score(df)
        # midpoint = 100, range = 40, range_pct = 40%
        assert abs(result.iloc[0]["range_pct"] - 40.0) < 0.01


# --- Dividend Score ---


class TestDividendScore:
    def test_more_years_scores_higher(self):
        df = make_stock_df({
            "dividend_years": [10, 1, 5, 5, 5],
            "latest_dividend_pct": [20, 20, 20, 20, 20],
        })
        result = calculate_dividend_score(df)
        assert result.iloc[0]["dividend_score"] > result.iloc[1]["dividend_score"]

    def test_higher_pct_scores_higher(self):
        df = make_stock_df({
            "dividend_years": [5, 5, 5, 5, 5],
            "latest_dividend_pct": [50, 10, 20, 20, 20],
        })
        result = calculate_dividend_score(df)
        assert result.iloc[0]["dividend_score"] > result.iloc[1]["dividend_score"]

    def test_no_dividends_scores_zero(self):
        df = make_stock_df({
            "dividend_years": [0, 5, 5, 5, 5],
            "latest_dividend_pct": [0, 20, 20, 20, 20],
        })
        result = calculate_dividend_score(df)
        assert result.iloc[0]["dividend_score"] == 0.0

    def test_weight_split(self):
        """60% years + 40% pct weighting."""
        df = make_stock_df({
            "dividend_years": [10, 10, 10, 10, 10],
            "latest_dividend_pct": [100, 100, 100, 100, 100],
        })
        result = calculate_dividend_score(df)
        # Max years, max pct → both normalized to 1.0
        # Score = 0.6 * 1.0 + 0.4 * 1.0 = 1.0
        assert abs(result.iloc[0]["dividend_score"] - 1.0) < 0.001


# --- Liquidity Score ---


class TestLiquidityScore:
    def test_higher_trades_score_higher(self):
        df = make_stock_df({"trade_count": [1000, 50, 200, 200, 200]})
        result = calculate_liquidity_score(df)
        assert result.iloc[0]["liquidity_score"] > result.iloc[1]["liquidity_score"]

    def test_zero_trades_scores_zero(self):
        df = make_stock_df({"trade_count": [0, 200, 200, 200, 200]})
        result = calculate_liquidity_score(df)
        assert result.iloc[0]["liquidity_score"] == 0.0

    def test_log_scaling(self):
        """Log scaling should reduce the dominance of outliers."""
        df = make_stock_df({"trade_count": [100000, 100, 200, 200, 200]})
        result = calculate_liquidity_score(df)
        # With linear scaling, stock1 would be 0.001. With log, it's much higher.
        assert result.iloc[1]["liquidity_score"] > 0.3


# --- P/E Score ---


class TestPEScore:
    def test_ideal_range_scores_one(self):
        """P/E 8-20 should get score 1.0."""
        df = make_stock_df({"pe_ratio": [15, 10, 8, 20, 12]})
        result = calculate_pe_score(df)
        assert (result["pe_score"] == 1.0).all()

    def test_moderate_range(self):
        """P/E 5-8 or 20-30 → 0.6."""
        df = make_stock_df({"pe_ratio": [6, 25, 7, 28, 5]})
        result = calculate_pe_score(df)
        assert (result["pe_score"] == 0.6).all()

    def test_extreme_range(self):
        """P/E < 5 or > 30 → 0.2."""
        df = make_stock_df({"pe_ratio": [3, 35, 2, 40, 1]})
        result = calculate_pe_score(df)
        assert (result["pe_score"] == 0.2).all()

    def test_null_pe_gets_neutral(self):
        """Missing P/E should get 0.5 (neutral)."""
        df = make_stock_df({"pe_ratio": [None, None, None, None, None]})
        result = calculate_pe_score(df)
        assert (result["pe_score"] == 0.5).all()


# --- Composite Score ---


class TestCompositeScore:
    def test_weights_sum_correctly(self):
        """Composite = 0.4*vol + 0.3*div + 0.2*liq + 0.1*pe."""
        df = make_stock_df()
        df["volatility_score"] = 1.0
        df["dividend_score"] = 1.0
        df["liquidity_score"] = 1.0
        df["pe_score"] = 1.0
        result = calculate_composite_score(df)
        assert abs(result.iloc[0]["stability_score"] - 1.0) < 0.001

    def test_weights_match_config(self):
        df = make_stock_df(n=1)
        df["volatility_score"] = 0.8
        df["dividend_score"] = 0.6
        df["liquidity_score"] = 0.4
        df["pe_score"] = 0.2
        result = calculate_composite_score(df)
        expected = (
            config.WEIGHT_VOLATILITY * 0.8
            + config.WEIGHT_DIVIDEND * 0.6
            + config.WEIGHT_LIQUIDITY * 0.4
            + config.WEIGHT_PE * 0.2
        )
        assert abs(result.iloc[0]["stability_score"] - expected) < 0.001

    def test_zero_scores_gives_zero(self):
        df = make_stock_df(n=1)
        df["volatility_score"] = 0.0
        df["dividend_score"] = 0.0
        df["liquidity_score"] = 0.0
        df["pe_score"] = 0.0
        result = calculate_composite_score(df)
        assert result.iloc[0]["stability_score"] == 0.0
