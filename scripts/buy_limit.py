# -*- coding: utf-8 -*-
"""
core/buy_limit.py 鈥?Place a limit buy order
Usage: python core/buy_limit.py SYMBOL PRICE AMOUNT_USDT
Example: python core/buy_limit.py BTC 58800 50
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


def buy_limit(symbol: str, price: float, cost_usdt: float):
    """Place a limit buy order at a specified price."""
    sym = f"{symbol.upper()}/USDT"
    ex = create_exchange()

    # Check balance
    bal = ex.fetch_balance()
    usdt_free = float(bal.get("USDT", {}).get("free", 0) or 0)
    print(f"USDT available: ${usdt_free:.2f}")

    if usdt_free < cost_usdt:
        print(f"Error: Insufficient USDT (${usdt_free:.2f} < ${cost_usdt:.2f})")
        sys.exit(1)

    # Current price for reference
    ticker = ex.fetch_ticker(sym)
    current_price = float(ticker["last"])
    print(f"Current {symbol.upper()} price: ${current_price:,.2f}")
    print(f"Target buy price: ${price:,.2f} ({((price - current_price) / current_price * 100):+.2f}% from current)")

    # Calculate qty
    qty = cost_usdt / price
    mkt = ex.market(sym)
    ap = mkt.get("precision", {}).get("amount", 8)
    if isinstance(ap, int):
        qty = math.floor(qty * 10**ap) / 10**ap
    else:
        qty = float(ex.amount_to_precision(sym, qty))

    print(f"Placing limit buy for {qty} {symbol.upper()} @ ${price:,.2f} (~${cost_usdt:.2f})...")

    order = ex.create_limit_buy_order(sym, qty, price)

    print(f"\n{'=' * 60}")
    print(f"  鉁?LIMIT BUY ORDER PLACED")
    print(f"{'=' * 60}")
    print(f"  Order ID:  {order.get('id', '?')}")
    print(f"  Status:    {order.get('status', '?')}")
    print(f"  Quantity:  {qty} {symbol.upper()}")
    print(f"  Price:     ${price:,.2f}")
    print(f"  Total:     ~${qty * price:.2f} USDT")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python buy_limit.py SYMBOL PRICE AMOUNT_USDT")
        print("Example: python buy_limit.py BTC 58800 50")
        sys.exit(1)
    buy_limit(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
