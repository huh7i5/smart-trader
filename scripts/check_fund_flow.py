"""
core/check_fund_flow.py �?Short-term fund flow analysis using Taker buy/sell
volume and order book depth.

Analyzes the last N hours of hourly candles to estimate whether buyers or
sellers dominate, and checks order book imbalance.

Usage: python core/check_fund_flow.py [--hours 6] [--symbols BTC SOL LINK DOGE]
"""
import sys, io, json, datetime, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ccxt

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_SYMBOLS = ["BTC/USDT", "SOL/USDT", "LINK/USDT", "DOGE/USDT"]


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


def analyze_fund_flow(ex, sym, hours=6):
    """Analyze fund flow for a single symbol over the last N hours."""
    klines = ex.fetch_ohlcv(sym, timeframe="1h", limit=hours)

    total_buy_vol = 0
    total_sell_vol = 0

    print(f"\n{'=' * 55}")
    print(f"  {sym}")
    print(f"{'=' * 55}")
    print(f"  {'Time':>6s} | {'Close':>10s} | {'Volume':>12s} | {'Net Flow':>14s}")
    print(f"  {'-' * 52}")

    for k in klines:
        dt = datetime.datetime.fromtimestamp(
            k[0] / 1000, datetime.timezone(datetime.timedelta(hours=8))
        ).strftime("%H:%M")
        o, h, l, c, vol = k[1], k[2], k[3], k[4], k[5]

        # Estimate buy/sell pressure from candle shape
        price_range = h - l
        if price_range > 0:
            buy_ratio = (c - l) / price_range
        else:
            buy_ratio = 0.5

        buy_vol = vol * buy_ratio
        sell_vol = vol * (1 - buy_ratio)
        net_flow = buy_vol - sell_vol

        total_buy_vol += buy_vol
        total_sell_vol += sell_vol

        sign = "+" if net_flow > 0 else ""
        tag = "🟢 BUY" if net_flow > 0 else "🔴 SELL"
        print(f"  {dt:>6s} | ${c:<9} | {vol:>12.2f} | {sign}{net_flow:>12.2f} {tag}")

    total_net = total_buy_vol - total_sell_vol
    sign = "+" if total_net > 0 else ""
    tag = "🟢 NET BUY" if total_net > 0 else "🔴 NET SELL"

    print(f"\n  {hours}h Buy Volume:  {total_buy_vol:>14.2f}")
    print(f"  {hours}h Sell Volume: {total_sell_vol:>14.2f}")
    print(f"  {hours}h Net Flow:    {sign}{total_net:>14.2f} {tag}")

    return {
        "symbol": sym,
        "buy_vol": total_buy_vol,
        "sell_vol": total_sell_vol,
        "net_flow": total_net,
        "is_net_buy": total_net > 0,
    }


def analyze_order_book(ex, sym="BTC/USDT", depth=20):
    """Analyze order book depth for bid/ask imbalance."""
    ob = ex.fetch_order_book(sym, limit=depth)
    total_bid = sum(b[1] for b in ob["bids"])
    total_ask = sum(a[1] for a in ob["asks"])
    bid_usd = sum(b[0] * b[1] for b in ob["bids"])
    ask_usd = sum(a[0] * a[1] for a in ob["asks"])
    ratio = total_bid / total_ask if total_ask > 0 else 0

    print(f"\n{'=' * 70}")
    print(f"  {sym} ORDER BOOK DEPTH (Top {depth} levels)")
    print(f"{'=' * 70}")
    print(f"  Bid (Buy) Wall:  {total_bid:.4f} ({sym.split('/')[0]}) (${bid_usd:,.0f})")
    print(f"  Ask (Sell) Wall: {total_ask:.4f} ({sym.split('/')[0]}) (${ask_usd:,.0f})")

    tag = "🟢 Buyers dominate" if ratio > 1 else "🔴 Sellers dominate"
    print(f"  Bid/Ask Ratio:   {ratio:.2f}x {tag}")

    spread = ob["asks"][0][0] - ob["bids"][0][0]
    print(f"  Best Bid: ${ob['bids'][0][0]:,.2f}  |  Best Ask: ${ob['asks'][0][0]:,.2f}  |  Spread: ${spread:.2f}")

    return {"ratio": ratio, "buyers_dominate": ratio > 1}


def main():
    parser = argparse.ArgumentParser(description="Short-term fund flow analysis")
    parser.add_argument("--hours", type=int, default=6, help="Number of hours to analyze")
    parser.add_argument("--symbols", nargs="+", default=None, help="Symbols to analyze")
    args = parser.parse_args()

    symbols = args.symbols or DEFAULT_SYMBOLS
    symbols = [s if "/" in s else f"{s.upper()}/USDT" for s in symbols]

    ex = create_exchange()

    print("=" * 70)
    print(f"  SHORT-TERM FUND FLOW ANALYSIS (Last {args.hours} Hours)")
    print("=" * 70)

    results = []
    for sym in symbols:
        r = analyze_fund_flow(ex, sym, hours=args.hours)
        results.append(r)

    # Order book analysis for BTC
    ob_result = analyze_order_book(ex, "BTC/USDT")

    # Summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    for r in results:
        tag = "🟢 NET BUY" if r["is_net_buy"] else "🔴 NET SELL"
        print(f"  {r['symbol']:16s}: {tag}")
    tag = "🟢 BUYERS" if ob_result["buyers_dominate"] else "🔴 SELLERS"
    print(f"  BTC Order Book:   {tag} ({ob_result['ratio']:.2f}x)")


if __name__ == "__main__":
    main()
