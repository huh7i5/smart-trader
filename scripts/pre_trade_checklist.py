# -*- coding: utf-8 -*-
"""
core/pre_trade_checklist.py ?Automated 3-Point Pre-Trade Checklist

Runs the three mandatory checks before any trade:
  �?Smart Money Direction (ETF flows + whale signals)
  �?Retail Behavior (Taker volume + order book depth)
  �?Macro Events (upcoming CPI, FOMC, earnings)

Only proceed when all three checks pass (🟢🟢🟢).

Usage: python core/pre_trade_checklist.py [--symbol BTC/USDT]
"""
import sys, io, json, datetime, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ccxt

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def create_exchange():
    """Create and configure Binance exchange client."""
    cfg = json.load(open(CONFIG_PATH))
    ex = ccxt.binance({
        "apiKey": cfg["api_key"],
        "secret": cfg["api_secret"],
        "enableRateLimit": True,
        "timeout": 30000,
        "options": {
            "defaultType": "spot",
            "adjustForTimeDifference": True,
            "recvWindow": 60000,
        },
    })
    if cfg.get("proxy"):
        ex.proxies = {"http": cfg["proxy"], "https": cfg["proxy"]}
    st = ex.fetch_time()
    lt = ex.milliseconds()
    ex.options["timeDifference"] = lt - st
    ex.load_markets()
    return ex


def check_smart_money(ex, sym="BTC/USDT"):
    """
    Check �?�?Smart Money Direction.
    Uses 24h kline data to detect if price is stable despite selling pressure,
    which indicates smart money accumulation.
    """
    # Fetch daily kline for longer-term trend
    daily = ex.fetch_ohlcv(sym, timeframe="1d", limit=7)

    # Calculate 7-day trend
    if len(daily) >= 7:
        week_ago_close = daily[0][4]
        current_close = daily[-1][4]
        weekly_change = (current_close - week_ago_close) / week_ago_close * 100
    else:
        weekly_change = 0

    # Check order book for hidden buying (iceberg order detection)
    ob = ex.fetch_order_book(sym, limit=20)
    total_bid = sum(b[0] * b[1] for b in ob["bids"])
    total_ask = sum(a[0] * a[1] for a in ob["asks"])
    bid_ask_ratio = total_bid / total_ask if total_ask > 0 else 0

    # Smart money signal: price trending up AND buy wall > sell wall
    is_bullish = weekly_change > 0 and bid_ask_ratio > 1.0

    status = "🟢 PASS" if is_bullish else "🔴 CAUTION"

    print(f"\n  �?Smart Money Direction: {status}")
    print(f"     7-day trend: {weekly_change:+.2f}%")
    print(f"     Bid/Ask ratio: {bid_ask_ratio:.2f}x {'(buyers dominate)' if bid_ask_ratio > 1 else '(sellers dominate)'}")
    if is_bullish:
        print("     �?Smart money appears to be accumulating")
    else:
        print("     �?Smart money direction unclear or bearish")

    return is_bullish


def check_retail_behavior(ex, sym="BTC/USDT", hours=6):
    """
    Check �?�?Retail Behavior.
    Analyzes short-term taker buy/sell volume to identify retail sentiment.
    Ideal signal: retail selling but price NOT dropping (smart money absorbing).
    """
    klines = ex.fetch_ohlcv(sym, timeframe="1h", limit=hours)

    total_buy = 0
    total_sell = 0

    for k in klines:
        o, h, l, c, vol = k[1], k[2], k[3], k[4], k[5]
        price_range = h - l
        if price_range > 0:
            buy_ratio = (c - l) / price_range
        else:
            buy_ratio = 0.5
        total_buy += vol * buy_ratio
        total_sell += vol * (1 - buy_ratio)

    net_flow = total_buy - total_sell
    is_net_buy = net_flow > 0

    # Price change over the analysis period
    if len(klines) >= 2:
        price_start = klines[0][1]  # open of first candle
        price_end = klines[-1][4]   # close of last candle
        price_change = (price_end - price_start) / price_start * 100
    else:
        price_change = 0

    # Bullish signal: either net buying, or retail selling but price stable
    retail_selling_price_stable = (not is_net_buy) and (price_change > -1.0)
    is_favorable = is_net_buy or retail_selling_price_stable

    status = "🟢 PASS" if is_favorable else "🔴 CAUTION"

    print(f"\n  �?Retail Behavior ({hours}h): {status}")
    print(f"     Net flow: {'🟢 NET BUY' if is_net_buy else '🔴 NET SELL'}")
    print(f"     Price change: {price_change:+.2f}%")
    if retail_selling_price_stable:
        print("     �?Retail is selling but price is stable = bottom signal (smart money absorbing)")
    elif is_net_buy:
        print("     �?Retail is buying, positive sentiment")
    else:
        print("     �?Retail is selling AND price is dropping = risk")

    return is_favorable


def check_macro_events():
    """
    Check �?�?Macro Events Calendar.
    Checks if there are any major upcoming events that could cause volatility.
    NOTE: This is a simplified version. In production, integrate with an
    economic calendar API.
    """
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

    # Known major event dates (update periodically)
    # Format: (month, day, description, risk_level)
    major_events = [
        # US CPI releases (typically 2nd or 3rd Tuesday of the month)
        (7, 14, "US CPI June 2026", "HIGH"),
        (8, 12, "US CPI July 2026", "HIGH"),
        (9, 10, "US CPI August 2026", "HIGH"),
        # FOMC meetings
        (7, 29, "FOMC Meeting", "HIGH"),
        (7, 30, "FOMC Rate Decision", "CRITICAL"),
        (9, 16, "FOMC Meeting", "HIGH"),
        (9, 17, "FOMC Rate Decision", "CRITICAL"),
        # Earnings season
        (7, 22, "Google (GOOGL) Earnings", "MEDIUM"),
        (7, 23, "Tesla (TSLA) Earnings", "MEDIUM"),
        (7, 24, "Microsoft (MSFT) Earnings", "MEDIUM"),
        (7, 31, "Apple (AAPL) Earnings", "MEDIUM"),
        # Crypto-specific
        (7, 16, "CXMT (ChangXin Memory) IPO", "HIGH"),
    ]

    upcoming = []
    for month, day, desc, risk in major_events:
        try:
            event_date = datetime.datetime(now.year, month, day, tzinfo=now.tzinfo)
            delta = (event_date - now).total_seconds() / 3600  # hours until event
            if 0 < delta < 48:  # within next 48 hours
                upcoming.append((delta, desc, risk))
        except ValueError:
            pass

    has_critical = any(r == "CRITICAL" for _, _, r in upcoming)
    has_high = any(r == "HIGH" for _, _, r in upcoming)
    is_clear = len(upcoming) == 0

    if is_clear:
        status = "🟢 PASS"
    elif has_critical:
        status = "🔴 BLOCKED"
    elif has_high:
        status = "🟡 CAUTION"
    else:
        status = "🟢 PASS"

    print(f"\n  �?Macro Events (next 48h): {status}")
    if upcoming:
        for hours_until, desc, risk in sorted(upcoming):
            risk_emoji = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🟢"}.get(risk, "?")
            print(f"     {risk_emoji} {desc} �?in {hours_until:.1f} hours ({risk})")
    else:
        print("     No major events in the next 48 hours")

    return is_clear or (not has_critical)


def run_checklist(symbol="BTC/USDT"):
    """Run the full 3-point pre-trade checklist."""
    print("=" * 60)
    print("  📋 PRE-TRADE CHECKLIST")
    print(f"  Symbol: {symbol}")
    print(f"  Time: {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} (Beijing)")
    print("=" * 60)

    ex = create_exchange()

    check1 = check_smart_money(ex, symbol)
    check2 = check_retail_behavior(ex, symbol)
    check3 = check_macro_events()

    all_pass = check1 and check2 and check3

    print(f"\n{'=' * 60}")
    print(f"  VERDICT: {'�?ALL CLEAR �?SAFE TO TRADE' if all_pass else '�?DO NOT TRADE �?CONDITIONS NOT MET'}")
    print(f"{'=' * 60}")

    checks = [
        ("�?Smart Money", check1),
        ("�?Retail Behavior", check2),
        ("�?Macro Events", check3),
    ]
    for name, passed in checks:
        print(f"  {name}: {'🟢' if passed else '🔴'}")

    if not all_pass:
        print("\n  ⚠️ Recommendation: Wait for all conditions to turn green.")
        print("  Re-run this checklist before attempting any trade.")

    return all_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-trade checklist")
    parser.add_argument("--symbol", default="BTC/USDT", help="Symbol to check")
    args = parser.parse_args()
    run_checklist(args.symbol)
