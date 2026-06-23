"""
DSE Portfolio Verification Script
Run this ON THE DAY you plan to buy to confirm data freshness and stock health.

1. Automated cross-validation: re-scrapes each recommended stock and compares
   against the saved recommendations CSV for data drift.
2. Manual due-diligence checklist: generates output/due_diligence.md

Output:
  - Console report with PASS/WARN/FAIL verdicts per stock
  - output/verification_report.txt
  - output/due_diligence.md
"""

import csv
import os
import sys
import time
from datetime import datetime

import pandas as pd

import config
from scraper import get_session, scrape_company_detail, scrape_latest_prices


def load_recommendations():
    """Load recommended portfolio from CSV."""
    if not os.path.exists(config.RECOMMENDATIONS_CSV):
        print(f"ERROR: {config.RECOMMENDATIONS_CSV} not found. Run allocator.py first.")
        sys.exit(1)
    return pd.read_csv(config.RECOMMENDATIONS_CSV)


def verify_stock(session, ticker, saved_row, current_prices):
    """
    Cross-validate a single stock against fresh data.
    Returns (verdict, reasons) where verdict is PASS/WARN/FAIL.
    """
    reasons = []
    verdict = "PASS"

    # Get fresh company detail
    detail = scrape_company_detail(session, ticker)
    if not detail:
        return "FAIL", ["Could not fetch company page — stock may be suspended"]

    # Check 1: Current LTP vs saved LTP
    current_ltp = current_prices.get(ticker, {}).get("ltp")
    saved_ltp = saved_row["ltp"]

    if current_ltp is None:
        verdict = "FAIL"
        reasons.append(f"Ticker not found in latest prices — may be halted/delisted")
    elif saved_ltp and saved_ltp > 0:
        pct_change = abs(current_ltp - saved_ltp) / saved_ltp * 100
        if pct_change > 10:
            verdict = "FAIL"
            reasons.append(f"Price moved {pct_change:.1f}% (was {saved_ltp}, now {current_ltp}) — STALE DATA, re-run scraper")
        elif pct_change > 5:
            verdict = max(verdict, "WARN")
            reasons.append(f"Price moved {pct_change:.1f}% (was {saved_ltp}, now {current_ltp})")
        else:
            reasons.append(f"Price stable ({pct_change:.1f}% change: {saved_ltp} → {current_ltp})")

    # Check 2: Market Category still A
    cat = detail.get("market_category")
    if cat and cat != "A":
        verdict = "FAIL"
        reasons.append(f"Market category downgraded to '{cat}' — DO NOT BUY")
    elif cat == "A":
        reasons.append("Category A confirmed")

    # Check 3: Sector unchanged
    sector = detail.get("sector")
    saved_sector = saved_row.get("sector", "")
    if sector and saved_sector and sector != saved_sector:
        verdict = "FAIL"
        reasons.append(f"Sector changed: was '{saved_sector}', now '{sector}'")
    elif sector:
        reasons.append(f"Sector: {sector}")

    # Check 4: P/E ratio sanity
    pe = detail.get("pe_ratio")
    if pe and pe > config.MAX_PE_RATIO:
        verdict = max(verdict, "WARN")
        reasons.append(f"P/E now {pe:.1f} — exceeds {config.MAX_PE_RATIO} threshold")
    elif pe:
        reasons.append(f"P/E: {pe:.1f}")

    # Check 5: 52-week range data still available
    if not detail.get("week52_high") or not detail.get("week52_low"):
        verdict = max(verdict, "WARN")
        reasons.append("52-week range data missing on company page")
    else:
        reasons.append(f"52wk: {detail['week52_low']:.1f} - {detail['week52_high']:.1f}")

    # Check 6: Dividend info present
    if not detail.get("latest_dividend_pct"):
        verdict = max(verdict, "WARN")
        reasons.append("No dividend data found on page")
    else:
        reasons.append(f"Dividend: {detail['latest_dividend_pct']}% ({detail.get('dividend_years', '?')} years)")

    return verdict, reasons


def generate_due_diligence(portfolio):
    """Generate a markdown due-diligence checklist for manual research."""
    lines = [
        "# Due Diligence Checklist",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "Complete ALL items below before placing buy orders.",
        "Mark [x] when verified. Any unchecked item = do NOT buy that stock.",
        "",
    ]

    for _, row in portfolio.iterrows():
        ticker = row["ticker"]
        sector = row.get("sector", "Unknown")
        ltp = row.get("ltp", 0)
        shares = int(row.get("shares_to_buy", 0))
        investment = row.get("investment_bdt", 0)

        lines.append(f"## {ticker}")
        lines.append(f"Sector: {sector} | LTP: {ltp} | Shares: {shares} | Investment: BDT {investment:,.0f}")
        lines.append("")
        lines.append(f"- [ ] **DSE Announcements**: Visit https://www.dsebd.org/displayCompany.php?name={ticker} — check 'Company News' section for recent disclosures, AGM notices, or adverse events")
        lines.append(f"- [ ] **Dividend Confirmed**: Verify the latest cash dividend was actually PAID (not just declared). Check if ex-dividend date has passed")
        lines.append(f"- [ ] **No Legal/Regulatory Issues**: Search DSE announcements for any BSEC show-cause notice, penalty, or trading restriction")
        lines.append(f"- [ ] **Not Halted**: Confirm stock traded on the most recent trading day (check trade count > 0)")
        lines.append(f"- [ ] **Face Value Check**: Confirm face value on company page matches our data (BDT {row.get('face_value', 10):.0f}) — a mismatch means a split occurred")
        lines.append(f"- [ ] **Quarterly Financials**: Check if revenue/profit is declining vs previous quarter (DSE company page → Financial Performance)")
        lines.append(f"- [ ] **News Search**: Google \"{ticker} Bangladesh 2026\" — any fraud, scandal, or governance issues?")
        lines.append(f"- [ ] **Dividend Type**: Confirm dividend is CASH (not stock dividend which doesn't provide income)")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Final Sign-Off")
    lines.append("")
    lines.append("- [ ] All stocks above verified — no FAIL items remaining")
    lines.append(f"- [ ] Brokerage account has >= BDT {config.TOTAL_BUDGET_BDT:,} available")
    lines.append("- [ ] Will place orders during market hours (10:00 AM - 2:30 PM BST)")
    lines.append("- [ ] Understand that stability ≠ guaranteed returns — this is a tax rebate strategy")
    lines.append("")

    os.makedirs("output", exist_ok=True)
    with open("output/due_diligence.md", "w") as f:
        f.write("\n".join(lines))

    print(f"\n✓ Due diligence checklist saved to output/due_diligence.md")


def run():
    """Main verification pipeline."""
    print("=" * 60)
    print("DSE PORTFOLIO VERIFICATION")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load saved recommendations
    portfolio = load_recommendations()
    tickers = portfolio["ticker"].tolist()
    print(f"Verifying {len(tickers)} stocks: {', '.join(tickers)}")

    # Get fresh data
    session = get_session()

    print("\nFetching current prices...")
    current_prices = scrape_latest_prices(session)
    time.sleep(config.REQUEST_DELAY_SECONDS)

    print(f"Verifying each stock against fresh company data...\n")

    results = []
    report_lines = [
        f"DSE Portfolio Verification Report",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Stocks: {len(tickers)}",
        "=" * 60,
        "",
    ]

    pass_count = 0
    warn_count = 0
    fail_count = 0

    for _, row in portfolio.iterrows():
        ticker = row["ticker"]
        print(f"  [{ticker}]", end=" ")

        verdict, reasons = verify_stock(session, ticker, row, current_prices)
        time.sleep(config.REQUEST_DELAY_SECONDS)

        # Color-code console output
        symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[verdict]
        print(f"{symbol} {verdict}")
        for r in reasons:
            print(f"      {r}")

        if verdict == "PASS":
            pass_count += 1
        elif verdict == "WARN":
            warn_count += 1
        else:
            fail_count += 1

        # Add to report
        report_lines.append(f"[{verdict}] {ticker} ({row.get('sector', '')})")
        for r in reasons:
            report_lines.append(f"      {r}")
        report_lines.append("")

        results.append({"ticker": ticker, "verdict": verdict, "reasons": reasons})

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {pass_count} PASS | {warn_count} WARN | {fail_count} FAIL")
    print("=" * 60)

    if fail_count > 0:
        print("\n⚠️  FAILED stocks should NOT be purchased until issues are resolved.")
        print("   Consider re-running scraper.py if prices are stale.")
    elif warn_count > 0:
        print("\n  Warnings are informational — review but likely safe to proceed.")
    else:
        print("\n✓ All stocks passed verification. Safe to proceed with purchases.")

    # Generate updated order sheet with current prices
    print("\n" + "-" * 60)
    print("ORDER SHEET (use current prices)")
    print("-" * 60)
    fee_mult = 1 + config.BROKERAGE_FEE_PCT / 100
    net_budget = config.TOTAL_BUDGET_BDT / fee_mult
    per_stock = net_budget / len(tickers)

    total_cost = 0
    for _, row in portfolio.iterrows():
        ticker = row["ticker"]
        current_ltp = current_prices.get(ticker, {}).get("ltp", row["ltp"])
        shares = int(per_stock // current_ltp)
        cost = shares * current_ltp
        total_cost += cost
        print(f"  {ticker:<12} @ BDT {current_ltp:>8.1f} × {shares:>4} shares = BDT {cost:>10,.0f}")

    total_fees = total_cost * config.BROKERAGE_FEE_PCT / 100
    print(f"\n  Shares total:  BDT {total_cost:>10,.0f}")
    print(f"  Fees (~0.3%):  BDT {total_fees:>10,.0f}")
    print(f"  Grand total:   BDT {total_cost + total_fees:>10,.0f}")
    print(f"  Budget:        BDT {config.TOTAL_BUDGET_BDT:>10,.0f}")
    print(f"  Remaining:     BDT {config.TOTAL_BUDGET_BDT - total_cost - total_fees:>10,.0f}")

    # Save report
    report_lines.append("=" * 60)
    report_lines.append(f"RESULTS: {pass_count} PASS | {warn_count} WARN | {fail_count} FAIL")
    report_lines.append("=" * 60)

    os.makedirs("output", exist_ok=True)
    with open("output/verification_report.txt", "w") as f:
        f.write("\n".join(report_lines))
    print(f"\n✓ Full report saved to output/verification_report.txt")

    # Generate due diligence checklist
    generate_due_diligence(portfolio)


if __name__ == "__main__":
    run()
