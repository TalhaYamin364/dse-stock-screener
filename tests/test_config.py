"""
Unit tests for config validation.
Ensures config values are internally consistent.
"""

import config


class TestConfigWeights:
    def test_weights_sum_to_one(self):
        total = (
            config.WEIGHT_VOLATILITY
            + config.WEIGHT_DIVIDEND
            + config.WEIGHT_LIQUIDITY
            + config.WEIGHT_PE
        )
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_all_weights_positive(self):
        assert config.WEIGHT_VOLATILITY > 0
        assert config.WEIGHT_DIVIDEND > 0
        assert config.WEIGHT_LIQUIDITY > 0
        assert config.WEIGHT_PE > 0


class TestConfigBudget:
    def test_budget_positive(self):
        assert config.TOTAL_BUDGET_BDT > 0

    def test_fee_percentage_reasonable(self):
        """Fee should be between 0 and 5%."""
        assert 0 < config.BROKERAGE_FEE_PCT < 5

    def test_target_stocks_positive(self):
        assert config.TARGET_STOCKS > 0

    def test_max_per_sector_positive(self):
        assert config.MAX_PER_SECTOR > 0

    def test_max_per_sector_less_than_target(self):
        assert config.MAX_PER_SECTOR < config.TARGET_STOCKS


class TestConfigFilters:
    def test_max_pe_positive(self):
        assert config.MAX_PE_RATIO > 0

    def test_min_trade_count_positive(self):
        assert config.MIN_TRADE_COUNT > 0

    def test_market_category_whitelist_not_empty(self):
        assert len(config.MARKET_CATEGORY_WHITELIST) > 0

    def test_excluded_sectors_is_list(self):
        assert isinstance(config.EXCLUDED_SECTORS, list)

    def test_excluded_tickers_is_list(self):
        assert isinstance(config.EXCLUDED_TICKERS, list)
