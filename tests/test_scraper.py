"""
Unit tests for the scraper helper functions.
Only tests pure logic functions — no network calls.
"""

import pytest

from scraper import _parse_number, _next_nonempty, is_banking_sector


# --- _parse_number ---


class TestParseNumber:
    def test_simple_float(self):
        assert _parse_number("123.45") == 123.45

    def test_integer_string(self):
        assert _parse_number("100") == 100.0

    def test_with_commas(self):
        assert _parse_number("1,234,567.89") == 1234567.89

    def test_dash_returns_none(self):
        assert _parse_number("-") is None

    def test_double_dash_returns_none(self):
        assert _parse_number("--") is None

    def test_empty_string_returns_none(self):
        assert _parse_number("") is None

    def test_none_input_returns_none(self):
        assert _parse_number(None) is None

    def test_whitespace_stripped(self):
        assert _parse_number("  42.50  ") == 42.50

    def test_non_numeric_returns_none(self):
        assert _parse_number("abc") is None


# --- _next_nonempty ---


class TestNextNonempty:
    def test_immediate_next(self):
        lines = ["Label", "Value", "Other"]
        assert _next_nonempty(lines, 0) == "Value"

    def test_skips_empty_lines(self):
        lines = ["Label", "", "", "Value", "Other"]
        assert _next_nonempty(lines, 0) == "Value"

    def test_all_empty_returns_none(self):
        lines = ["Label", "", "", "", "", ""]
        assert _next_nonempty(lines, 0) is None

    def test_respects_5_line_window(self):
        """Only looks ahead 4 lines after start_idx."""
        lines = ["Label", "", "", "", "", "TooFar"]
        assert _next_nonempty(lines, 0) is None

    def test_end_of_list(self):
        lines = ["Only"]
        assert _next_nonempty(lines, 0) is None


# --- is_banking_sector ---


class TestIsBankingSector:
    def test_bank_lowercase(self):
        assert is_banking_sector("Bank") is True

    def test_banking_substring(self):
        assert is_banking_sector("Commercial Banking") is True

    def test_non_banking(self):
        assert is_banking_sector("Pharmaceuticals & Chemicals") is False

    def test_none_input(self):
        assert is_banking_sector(None) is False

    def test_empty_string(self):
        assert is_banking_sector("") is False

    def test_case_insensitive(self):
        assert is_banking_sector("BANKING") is True
