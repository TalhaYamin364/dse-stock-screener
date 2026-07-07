# DSE Stock Screener — Tasks

## Build History

### Phase 1: Screening Pipeline (completed Jun 25, 2026)
- [x] scraper.py — fetch all DSE stock prices + company details
- [x] analyzer.py — filter + composite stability scoring
- [x] allocator.py — equal-weight allocation with sector cap
- [x] verify.py — pre-trade verification with fresh prices
- [x] config.py — centralized tunable parameters + .env support
- [x] Unit tests (74 passing) — synthetic data, no network
- [x] .env.example + .gitignore + README

### Phase 2: Portfolio Tracker (completed Jul 5, 2026)
- [x] tracker.py — reads trades.csv, fetches live prices, outputs P&L + signals
- [x] trades.csv — trade journal (all buys Jun 25 + SPCL sell Jul 5)
- [x] Signal logic: SELL / NEAR TARGET / HOLD / WATCH / STOP
- [x] Realized P&L computed from closed trades
- [x] output/snapshots.csv — appending daily snapshots
- [x] Updated README, .gitignore, copilot-instructions

### Key Decisions Log
| Date | Decision | Why |
|------|----------|-----|
| Jun 25 | Excluded NHFIL permanently | Fake low P/E from unaudited Q1 EPS extrapolation; audited P/E was 886x |
| Jun 25 | Excluded MARICO, APEXFOOT | Failed due diligence (thin liquidity, poor fundamentals) |
| Jul 5 | Sold SPCL at 58.00 (+6.4%) | Hit +6% target → automatic sell per rules |
| Jul 5 | Pivot from dividend to swing | Original strategy (buy Jun, hold for dividend) too slow for 5% target |
| Jul 5 | Adopted +6% / -3% rules | 2:1 reward-to-risk; daily noise is 1-3% so stop must be ≥3% |

---

## Current Portfolio Status (as of Jul 5, 2026)

- **Open positions**: 9 stocks (ACMELAB, BEACONPHAR, BERGERPBL, GP, LHB, OLYMPIC, PREMIERCEM, ROBI, SQURPHARMA)
- **Realized P&L**: +1,882 BDT (SPCL)
- **Unrealized P&L**: +2,258 BDT
- **Combined**: +4,140 BDT (24.9% of 16,650 target)
- **Cash freed**: ~35,025 BDT from SPCL sale (available for new swing trade)

---

## What's Next

### Immediate (Jul 7, next trading day)
- [ ] BEACONPHAR at +4.1% — place limit sell at 116-117 tonight for Monday fill
- [ ] ROBI at -2.2% — monitor; if opens below 32.0, market sell (stop breach)
- [ ] Run tracker.py during market hours for fresh snapshot
- [ ] Compare Mon snapshot to Sat snapshot for trend direction

### Short-term
- [ ] Decide on re-deploying SPCL cash (~35K BDT) into a new swing position
- [ ] Evaluate ACMELAB (+3.6%) — approaching sell zone, may need limit sell soon
- [ ] Add unit tests for tracker.py (load_positions, P&L calculation)

### Future Enhancements (not urgent)
- [ ] Multi-day trend comparison (diff between snapshots)
- [ ] 52-week high/low context in tracker output
- [ ] Alerts/notifications when signals trigger
- [ ] Backtest: simulate strategy on historical DSE data
