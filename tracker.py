"""
DSE Portfolio Tracker
Reads trades.csv, derives open positions, fetches live prices, and outputs
a snapshot with P&L signals.

Usage: python tracker.py

trades.csv format:
    date,ticker,side,shares,price,commission
    2026-06-25,ACMELAB,BUY,408,81.28,116.14
    2026-07-05,SPCL,SELL,606,58.00,123.02
"""

import csv
import os
from datetime import datetime

from scraper import get_session, scrape_latest_prices

TRADES_FILE = "trades.csv"
SNAPSHOT_FILE = "output/snapshots.csv"


def load_positions():
    """
    Read trades.csv and derive open positions + realized P&L.
    Returns (positions_list, realized_pnl).
    """
    buys = {}   # ticker -> list of {shares, price, commission}
    sells = {}  # ticker -> list of {shares, price, commission}

    with open(TRADES_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row["ticker"]
            entry = {
                "shares": int(row["shares"]),
                "price": float(row["price"]),
                "commission": float(row["commission"]),
            }
            if row["side"] == "BUY":
                buys.setdefault(ticker, []).append(entry)
            else:
                sells.setdefault(ticker, []).append(entry)

    # Derive open positions and realized P&L
    positions = []
    realized_pnl = 0.0

    for ticker, buy_list in buys.items():
        total_buy_shares = sum(b["shares"] for b in buy_list)
        total_buy_cost = sum(b["shares"] * b["price"] for b in buy_list)
        total_buy_commission = sum(b["commission"] for b in buy_list)
        # All-in cost per share (execution price + commission spread across shares)
        avg_cost = (total_buy_cost + total_buy_commission) / total_buy_shares

        total_sell_shares = 0
        total_sell_proceeds = 0.0
        total_sell_commission = 0.0
        for s in sells.get(ticker, []):
            total_sell_shares += s["shares"]
            total_sell_proceeds += s["shares"] * s["price"]
            total_sell_commission += s["commission"]

        # Realized P&L for closed portion
        if total_sell_shares > 0:
            # Cost of sold shares = shares × all-in avg cost (commission already in avg_cost)
            cost_of_sold = total_sell_shares * avg_cost
            realized_pnl += (
                total_sell_proceeds - cost_of_sold - total_sell_commission
            )

        # Open position (remaining shares)
        remaining = total_buy_shares - total_sell_shares
        if remaining > 0:
            positions.append({
                "ticker": ticker,
                "shares": remaining,
                "avg_cost": avg_cost,
            })

    return positions, realized_pnl


def take_snapshot():
    """Fetch current prices and calculate P&L for each position."""
    positions, realized_pnl = load_positions()

    session = get_session()
    prices = scrape_latest_prices(session)

    today = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")

    rows = []
    total_cost = 0
    total_market = 0
    total_pnl = 0

    for pos in positions:
        ticker = pos["ticker"]
        if ticker not in prices:
            print(f"  WARNING: {ticker} not found in today's prices")
            continue

        ltp = prices[ticker]["ltp"]
        shares = pos["shares"]
        avg_cost = pos["avg_cost"]

        cost_basis = shares * avg_cost
        market_value = shares * ltp
        unrealized_pnl = market_value - cost_basis
        pnl_pct = (ltp - avg_cost) / avg_cost * 100

        # Sell target (+6%) and stop-loss (-3%)
        target_price = avg_cost * 1.06
        stop_price = avg_cost * 0.97

        day_low = prices[ticker].get("low", 0)
        day_high = prices[ticker].get("high", 0)
        day_range_pct = ((day_high - day_low) / avg_cost * 100) if day_low else 0

        rows.append({
            "date": today,
            "time": time_str,
            "ticker": ticker,
            "shares": shares,
            "avg_cost": avg_cost,
            "ltp": ltp,
            "pnl_bdt": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "target_price": round(target_price, 2),
            "stop_price": round(stop_price, 2),
            "day_low": day_low,
            "day_high": day_high,
            "day_range_pct": round(day_range_pct, 2),
            "volume": prices[ticker].get("volume", 0),
            "trades": prices[ticker].get("trade_count", 0),
        })

        total_cost += cost_basis
        total_market += market_value
        total_pnl += unrealized_pnl

    if not rows:
        print("ERROR: No prices found for any position. Market may be closed.")
        return []

    # Write/append to CSV
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    file_exists = os.path.exists(SNAPSHOT_FILE)
    with open(SNAPSHOT_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    # Print summary
    print(f"\n{'='*60}")
    print(f"PORTFOLIO SNAPSHOT — {today} {time_str}")
    print(f"{'='*60}")
    print(f"{'Ticker':<12} {'LTP':>8} {'P&L %':>7} {'P&L BDT':>9} "
          f"{'Target':>8} {'Stop':>8} {'Signal':<10}")
    print(f"{'-'*12} {'-'*8} {'-'*7} {'-'*9} {'-'*8} {'-'*8} {'-'*10}")

    for r in sorted(rows, key=lambda x: x["pnl_pct"], reverse=True):
        if r["pnl_pct"] >= 6.0:
            signal = "** SELL **"
        elif r["pnl_pct"] >= 4.0:
            signal = "NEAR TARGET"
        elif r["pnl_pct"] <= -3.0:
            signal = "!! STOP !!"
        elif r["pnl_pct"] <= -1.5:
            signal = "WATCH"
        else:
            signal = "HOLD"

        print(f"{r['ticker']:<12} {r['ltp']:>8.1f} {r['pnl_pct']:>+6.1f}% "
              f"{r['pnl_bdt']:>+9.0f} {r['target_price']:>8.1f} "
              f"{r['stop_price']:>8.1f} {signal:<10}")

    print(f"{'-'*60}")
    print(f"{'TOTAL':<12} {'':>8} {total_pnl/total_cost*100:>+6.1f}% "
          f"{total_pnl:>+9.0f}")
    print(f"\n  Total cost basis:  BDT {total_cost:,.0f}")
    print(f"  Current value:     BDT {total_market:,.0f}")
    print(f"  Unrealized P&L:    BDT {total_pnl:,.0f}")
    print(f"  Realized P&L:      BDT {realized_pnl:+,.0f}")
    print(f"  Combined P&L:      BDT {total_pnl + realized_pnl:,.0f}")
    print(f"  Target (5%):       BDT 16,650")
    print(f"  Progress:          {(total_pnl + realized_pnl) / 16650 * 100:.1f}%")

    print(f"\n✓ Snapshot appended to {SNAPSHOT_FILE}")
    return rows


if __name__ == "__main__":
    take_snapshot()
