# DSE Stable Stock Screener

A data-driven stock screening tool for the **Dhaka Stock Exchange (DSE)**, built for use with **Shanta Securities' Easy Trade** platform.

Scrapes DSE market data, scores stocks on stability metrics, and outputs a diversified equal-weight portfolio allocation ready to execute.

## Purpose

Tax rebate investment (Section 76A) — identify stable, liquid, dividend-paying stocks suitable for short-term holds with minimal downside risk.

## Pipeline

```
scraper.py → analyzer.py → allocator.py → verify.py
```

| Step | What it does | Output |
|------|-------------|--------|
| `scraper.py` | Scrapes latest prices + company details from DSE | `output/raw_stock_data.csv` |
| `analyzer.py` | Scores stocks on volatility, dividends, liquidity, P/E | `output/analyzed_stocks.csv` |
| `allocator.py` | Equal-weight allocation across top diversified picks | `output/recommendations.csv` |
| `verify.py` | Re-fetches live prices, confirms nothing changed | `output/verification_report.txt` |
| `tracker.py` | Portfolio snapshot — live P&L, sell/hold signals | `output/snapshots.csv` |

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up personal config
cp .env.example .env
# Edit .env with your budget and any ticker exclusions

python scraper.py    # ~3 min (386 stocks, 0.5s delay each)
python analyzer.py   # instant
python allocator.py  # instant
python verify.py     # ~30s (re-fetches 10 stocks)
```

## Environment Variables

Personal configuration lives in a `.env` file (gitignored). Copy `.env.example` to get started:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DSE_BUDGET_BDT` | 100000 | Your BO account balance in BDT |
| `DSE_EXCLUDED_TICKERS` | *(empty)* | Comma-separated tickers to skip (e.g. `TICK1,TICK2`) |

## Configuration

All tunable parameters live in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TOTAL_BUDGET_BDT` | 100,000 | Total BO account balance to allocate (override with `DSE_BUDGET_BDT` env var) |
| `BROKERAGE_FEE_PCT` | 0.35 | Commission % (Shanta Securities Easy Trade) |
| `TARGET_STOCKS` | 10 | Number of positions |
| `MAX_PER_SECTOR` | 3 | Sector diversity cap |
| `EXCLUDED_SECTORS` | banking | Sectors to skip entirely |
| `EXCLUDED_TICKERS` | *(none)* | Set `DSE_EXCLUDED_TICKERS` env var (comma-separated) |
| `MAX_PE_RATIO` | 40 | Filter out overvalued stocks |
| `MIN_TRADE_COUNT` | 50 | Minimum daily trades (liquidity) |

## Stability Scoring

Composite score (0–1) with configurable weights:

- **Volatility (40%)** — 52-week range as % of midpoint. Tighter = better.
- **Dividend (30%)** — Years of dividend history + recent payout magnitude.
- **Liquidity (20%)** — Daily trade count (log-scaled).
- **P/E Ratio (10%)** — Ideal range 8–20; penalizes extremes.

## Allocation Logic

1. Divide budget equally across `TARGET_STOCKS` positions
2. Walk down ranked list, skip if sector cap reached
3. Calculate shares: `floor(budget_per_stock / (price × 1.0035))`
4. Commission (0.35%) is ON TOP of order value — matches Easy Trade's "Net Value"

## Broker Details (Shanta Securities)

- **Platform**: Easy Trade (Android/iOS)
- **Order type**: Limit, DAY
- **Commission**: 0.35% of order value
- **Net Value** = Order Value + Commission (deducted from BO balance)
- **Market**: DSE (Dhaka Stock Exchange)

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## Project Structure

```
dse-stock-screener/
├── config.py          # All tunable parameters (reads from .env)
├── scraper.py         # DSE web scraper
├── analyzer.py        # Stability scoring engine
├── allocator.py       # Portfolio allocation
├── verify.py          # Pre-trade verification
├── tracker.py         # Portfolio tracker (reads trades.csv, fetches live prices)
├── trades.csv         # Trade journal — all buys/sells (gitignored, personal)
├── requirements.txt   # Python dependencies
├── .env.example       # Template for personal config
├── .env               # Your personal config (gitignored)
├── tests/             # Unit tests
│   ├── test_analyzer.py
│   ├── test_allocator.py
│   ├── test_scraper.py
│   └── test_config.py
└── output/            # Generated CSVs (gitignored)
    └── snapshots.csv  # Appended daily by tracker.py
```

## Disclaimer

This is a personal screening tool, not financial advice. Past stability does not guarantee future performance. Verify each stock independently before investing.
