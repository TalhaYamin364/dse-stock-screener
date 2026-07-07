# DSE Stock Screener — Context

## Domain

**Market**: Dhaka Stock Exchange (DSE), Bangladesh
**Broker**: Shanta Securities — Easy Trade app (Android/iOS)
**Commission**: 0.35% ON TOP of order value (both buy AND sell = 0.70% round trip)
**Order type**: Limit, DAY only
**Market hours**: Sun–Thu, 10:00 AM – 2:30 PM (BST)
**Settlement**: T+2

---

## Trading Strategy

### Rules (confirmed Jul 5, 2026)
- **Target**: +6% per stock (nets ~5.3% after round-trip commission)
- **Stop-loss**: -3% per stock
- **Reward-to-risk**: 2:1 — only need ~40% win rate to break even
- **Portfolio target**: 5% total return on 333,000 BDT = 16,650 BDT profit
- **Max swing exposure**: ~200,000 BDT at any time
- **Position sizing**: Equal-weight across 10 stocks (~33,300 per position)
- **Sector cap**: Max 3 stocks per sector

### Signal Thresholds (tracker.py)
| P&L % | Signal | Action |
|--------|--------|--------|
| ≥ +6% | ** SELL ** | Place limit sell immediately |
| +4% to +6% | NEAR TARGET | Tighten stop, prepare sell order |
| -1.5% to +4% | HOLD | Do nothing |
| -1.5% to -3% | WATCH | Monitor closely, don't average down |
| ≤ -3% | !! STOP !! | Exit immediately, no exceptions |

### Key Lessons Learned
- Place limit orders at **ask price** (not bid) for guaranteed fill on buys
- Queue orders at night → priority in morning order book, no emotional hesitation
- DSE daily noise is 1-3% → stop-loss must be ≥3% to avoid constant triggers
- NHFIL had fake low P/E (unaudited Q1 EPS extrapolated) → always verify audited financials
- Statement "Avg. Cost" = all-in per-share cost (execution price + commission embedded)

---

## Architecture

### Screening Pipeline (run once to pick stocks)
```
scraper.py → analyzer.py → allocator.py → verify.py
```
- `scraper.py`: Fetches all 386 DSE stock prices + company details (rate-limited, 0.5s/stock)
- `analyzer.py`: Filters (Category A, P/E ≤40, ≥50 trades) + composite stability score
- `allocator.py`: Equal-weight allocation with sector cap, excludes tickers from .env
- `verify.py`: Re-fetches live prices, confirms stability for final order sheet

### Portfolio Tracker (run daily during market hours)
```
trades.csv → tracker.py → output/snapshots.csv
```
- `trades.csv`: Trade journal — source of truth for all buys/sells (gitignored)
- `tracker.py`: Reads trades.csv, derives open positions + realized P&L, fetches live prices
- `output/snapshots.csv`: Appended daily — multi-day trend data for analysis

### Data Flow
```
trades.csv (manual entry)
     ↓
tracker.py reads → load_positions() → (open_positions, realized_pnl)
     ↓
scraper.get_session() + scrape_latest_prices() → live DSE prices
     ↓
P&L calculation + signal generation
     ↓
output/snapshots.csv (append) + terminal summary
```

---

## File Roles

| File | Role | Gitignored? |
|------|------|-------------|
| `config.py` | All tunable parameters (reads .env) | No |
| `scraper.py` | DSE web scraper | No |
| `analyzer.py` | Stability scoring engine | No |
| `allocator.py` | Portfolio allocation | No |
| `verify.py` | Pre-trade verification | No |
| `tracker.py` | Portfolio tracker (daily snapshots) | No |
| `trades.csv` | Trade journal (personal financial data) | Yes |
| `.env` | Personal config (budget, exclusions) | Yes |
| `output/` | All generated CSVs | Yes |
| `learning-tracker.md` | Personal learning notes | Yes |
| `.github/copilot-instructions.md` | Copilot context (personal) | Yes |

---

## trades.csv Format

```csv
date,ticker,side,shares,price,commission
2026-06-25,ACMELAB,BUY,408,81.00,115.67
2026-07-05,SPCL,SELL,606,58.00,123.02
```

- `price`: Raw execution price (what the market filled at)
- `commission`: Actual commission charged (0.35% of amount)
- NOT the all-in avg cost from the broker statement
- tracker.py derives all-in cost as: `(shares × price + commission) / shares`

---

## Environment Variables (.env)

| Variable | Current Value | Description |
|----------|--------------|-------------|
| `DSE_BUDGET_BDT` | 333000 | Total BO account balance |
| `DSE_EXCLUDED_TICKERS` | MARICO,APEXFOOT,NHFIL | Tickers to never recommend |

---

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| `verify=False` on requests | DSE SSL cert chain incomplete — no fix available |
| 0.5s delay between requests | Respectful rate-limiting for DSE servers |
| `math.floor()` for shares | Never exceed budget (round up = overdraw BO account) |
| Category A filter | Most regulated tier, least manipulation risk |
| Banking sector excluded | Regulatory risk + low stability scores |
| Composite scoring (4 factors) | Single score balances volatility, dividends, liquidity, value |
| trades.csv over database | Simple, portable, manually editable, git-diffable |
