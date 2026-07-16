# -*- coding: utf-8 -*-
"""
core/buy_market.py 鈥?Execute a market buy order
Usage: python core/buy_market.py SYMBOL AMOUNT_USDT
Example: python core/buy_market.py BTC 50
"""
import sys, io, json, math
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ccxt

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def create_exchange():
    cfg = json.load(open(CONFIG_PATH))
    ex = ccxt.binance({
        "apiKey": cfg["api_key"],
        "secret": cfg["api_secret"],
        "enableRateLimit": True,
        "timeout": 60000,
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


def buy_market(symbol: str, cost_usdt: float):
    """Execute a market buy order for a given USDT amount."""
    sym = f"{symbol.upper()}/USDT"
    ex = create_exchange()

    # Check balance
    bal = ex.fetch_balance()
    usdt_free = float(bal.get("USDT", {}).get("free", 0) or 0)
    print(f"USDT available: ${usdt_free:.2f}")

    if usdt_free < cost_usdt:
        print(f"Error: Insufficient USDT (${usdt_free:.2f} < ${cost_usdt:.2f})")
        sys.exit(1)

    # Get current price
    ticker = ex.fetch_ticker(sym)
    current_price = float(ticker["last"])
    print(f"Current {symbol.upper()} price: ${current_price:,.2f}")

    # Calculate qty
    qty = cost_usdt / current_price
    mkt = ex.market(sym)
    ap = mkt.get("precision", {}).get("amount", 8)
    if isinstance(ap, int):
        qty = math.floor(qty * 10**ap) / 10**ap
    else:
        qty = float(ex.amount_to_precision(sym, qty))

    print(f"Placing market buy for {qty} {symbol.upper()} (~${cost_usdt:.2f})...")

    order = ex.create_market_buy_order(sym, qty)
    filled_price = float(order.get("average", 0) or order.get("price", 0) or current_price)
    filled_cost = float(order.get("cost", 0) or qty * filled_price)
    filled_qty = float(order.get("filled", 0) or qty)

    print(f"\n{'=' * 60}")
    print(f"  鉁?MARKET BUY COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Order ID:  {order.get('id', '?')}")
    print(f"  Status:    {order.get('status', '?')}")
    print(f"  Bought:    {filled_qty} {symbol.upper()}")
    print(f"  Avg Price: ${filled_price:,.2f}")
    print(f"  Spent:     ${filled_cost:.2f} USDT")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python buy_market.py SYMBOL AMOUNT_USDT")
        print("Example: python buy_market.py BTC 50")
        sys.exit(1)
    buy_market(sys.argv[1], float(sys.argv[2]))
