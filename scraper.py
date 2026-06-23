"""
DSE Stock Data Scraper
Scrapes stock data from dsebd.org:
  1. Latest share price page (all tickers + LTP + trade count + volume)
  2. Individual company pages (52-week range, sector, market category, P/E, dividends)

Filters out banking sector based on company page sector info.
Output: output/raw_stock_data.csv
"""

import csv
import os
import re
import time
import urllib3

import requests
from bs4 import BeautifulSoup

import config

# DSE's SSL certificate chain is incomplete on some systems.
# Since we're only reading public stock data, suppress the warning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_session():
    """Create a requests session with browser-like headers."""
    session = requests.Session()
    session.verify = False  # DSE cert chain issue on macOS
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return session


def scrape_latest_prices(session):
    """
    Scrape the latest share price page for all stocks.
    Returns a dict: {ticker: {ltp, high, low, closep, ycp, change, trade_count, volume}}
    """
    url = f"{config.DSE_BASE_URL}/latest_share_price_scroll_l.php"
    print(f"[1/2] Fetching latest share prices from {url}...")

    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    prices = {}

    # The correct data table has <th> headers including "TRADING CODE"
    target_table = None
    for table in soup.find_all("table"):
        ths = table.find_all("th")
        header_text = " ".join(th.get_text(strip=True) for th in ths)
        if "TRADING CODE" in header_text and "LTP" in header_text:
            target_table = table
            break

    if not target_table:
        print("  ERROR: Could not find the price data table")
        return prices

    rows = target_table.find_all("tr")
    for row in rows[1:]:  # Skip header row
        cells = row.find_all("td")
        if len(cells) < 11:
            continue

        try:
            # Columns: #, TRADING CODE, LTP, HIGH, LOW, CLOSEP, YCP, CHANGE, TRADE, VALUE, VOLUME
            ticker = cells[1].get_text(strip=True)

            if not ticker or ticker.startswith("TB") or "BOND" in ticker.upper():
                continue  # Skip treasury bonds

            ltp = _parse_number(cells[2].get_text(strip=True))
            high = _parse_number(cells[3].get_text(strip=True))
            low = _parse_number(cells[4].get_text(strip=True))
            closep = _parse_number(cells[5].get_text(strip=True))
            ycp = _parse_number(cells[6].get_text(strip=True))
            change = _parse_number(cells[7].get_text(strip=True))
            trade_count = _parse_number(cells[8].get_text(strip=True))
            value_mn = _parse_number(cells[9].get_text(strip=True))
            volume = _parse_number(cells[10].get_text(strip=True))

            if ltp and ltp > 0:
                prices[ticker] = {
                    "ltp": ltp,
                    "high": high,
                    "low": low,
                    "closep": closep,
                    "ycp": ycp,
                    "change": change,
                    "trade_count": int(trade_count) if trade_count else 0,
                    "value_mn": value_mn,
                    "volume": int(volume) if volume else 0,
                }
        except (IndexError, ValueError):
            continue

    print(f"  Found prices for {len(prices)} stocks")
    return prices


def scrape_company_detail(session, ticker):
    """
    Scrape individual company page for detailed info.
    Returns dict with: week52_high, week52_low, market_category, sector,
                       pe_ratio, dividend_pct, face_value
    """
    url = f"{config.DSE_BASE_URL}/displayCompany.php?name={ticker}"

    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ERROR fetching {ticker}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    data = {}

    # Parse line-by-line — DSE puts labels and values on separate lines
    page_text = soup.get_text()
    lines = [line.strip() for line in page_text.split("\n")]

    for i, line in enumerate(lines):
        # 52 Weeks' Moving Range — value is on the NEXT non-empty line
        # Format: "237.40 - 328.00"
        if "52 Weeks" in line and "Moving Range" in line:
            next_val = _next_nonempty(lines, i)
            if next_val:
                match = re.match(r"([\d,.]+)\s*-\s*([\d,.]+)", next_val)
                if match:
                    data["week52_low"] = _parse_number(match.group(1))
                    data["week52_high"] = _parse_number(match.group(2))

        # Sector — value on next line. Must be EXACTLY "Sector" (not "Sector wise...")
        elif line == "Sector":
            next_val = _next_nonempty(lines, i)
            if next_val and "wise" not in next_val.lower():
                data["sector"] = next_val

        # Market Category — value on next line (single letter like "A" or "Z")
        elif line == "Market Category":
            next_val = _next_nonempty(lines, i)
            if next_val and len(next_val) <= 2:
                data["market_category"] = next_val

        # Face Value — value on next line
        elif "Face Value" in line and "face_value" not in data:
            next_val = _next_nonempty(lines, i)
            if next_val:
                data["face_value"] = _parse_number(next_val)

        # Trailing P/E Ratio — concatenated values on next line like "11.2711.2811.33..."
        elif line == "Trailing P/E Ratio":
            next_val = _next_nonempty(lines, i)
            if next_val and next_val != "------":
                # Values are concatenated. Each is ~4-6 chars (e.g. "11.27")
                # Extract last complete number (most recent date)
                pe_matches = re.findall(r"\d+\.\d{2}", next_val)
                if pe_matches:
                    data["pe_ratio"] = _parse_number(pe_matches[-1])

    # Dividend info — search for percentage patterns after "Cash Dividend"
    page_text_joined = " ".join(lines)
    match = re.search(r"Cash Dividend\s+(.*?)(?:Bonus|Stock|Year End)", page_text_joined)
    if match:
        div_text = match.group(1)
        div_numbers = re.findall(r"(\d+)%", div_text)
        if div_numbers:
            data["latest_dividend_pct"] = float(div_numbers[0])
            data["dividend_years"] = len(div_numbers)

    return data


def _next_nonempty(lines, start_idx):
    """Return the next non-empty line after start_idx."""
    for j in range(start_idx + 1, min(start_idx + 5, len(lines))):
        if lines[j]:
            return lines[j]
    return None


def _parse_number(text):
    """Parse a number string, handling commas and edge cases."""
    if not text or text == "--" or text == "-":
        return None
    try:
        return float(text.replace(",", "").strip())
    except ValueError:
        return None


def is_banking_sector(sector_name):
    """Check if a sector name matches banking/financial exclusion list."""
    if not sector_name:
        return False
    sector_lower = sector_name.lower()
    for excluded in config.EXCLUDED_SECTORS:
        if excluded.lower() in sector_lower:
            return True
    return False


def run():
    """Main scraping pipeline."""
    session = get_session()

    # Step 1: Get all tickers + prices from the latest prices page
    latest_prices = scrape_latest_prices(session)
    time.sleep(config.REQUEST_DELAY_SECONDS)

    if not latest_prices:
        print("ERROR: No prices scraped. Check network or page structure.")
        return

    # Step 2: Scrape company details for each stock
    tickers = sorted(latest_prices.keys())
    print(f"\n[2/2] Fetching company details for {len(tickers)} stocks...")
    print("  This will take a few minutes (rate-limited to be polite to DSE servers)...")

    results = []
    banking_count = 0

    for i, ticker in enumerate(tickers, 1):
        if i % 25 == 0:
            print(f"  Progress: {i}/{len(tickers)} ({banking_count} banking excluded so far)")

        detail = scrape_company_detail(session, ticker)
        time.sleep(config.REQUEST_DELAY_SECONDS)

        if not detail:
            continue

        # Check if banking sector — skip if so
        sector = detail.get("sector", "Unknown")
        if is_banking_sector(sector):
            banking_count += 1
            continue

        # Merge data from price page + company page
        price_data = latest_prices[ticker]

        row = {
            "ticker": ticker,
            "sector": sector,
            "ltp": price_data.get("ltp"),
            "week52_high": detail.get("week52_high"),
            "week52_low": detail.get("week52_low"),
            "market_category": detail.get("market_category"),
            "pe_ratio": detail.get("pe_ratio"),
            "latest_dividend_pct": detail.get("latest_dividend_pct"),
            "dividend_years": detail.get("dividend_years", 0),
            "face_value": detail.get("face_value"),
            "trade_count": price_data.get("trade_count"),
            "volume": price_data.get("volume"),
        }
        results.append(row)

    # Write CSV
    os.makedirs("output", exist_ok=True)
    fieldnames = [
        "ticker", "sector", "ltp", "week52_high", "week52_low",
        "market_category", "pe_ratio", "latest_dividend_pct",
        "dividend_years", "face_value", "trade_count", "volume",
    ]

    with open(config.RAW_DATA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n  Excluded {banking_count} banking-sector stocks")
    print(f"✓ Saved {len(results)} non-banking stocks to {config.RAW_DATA_CSV}")
    print(f"  Columns: {', '.join(fieldnames)}")


if __name__ == "__main__":
    run()
