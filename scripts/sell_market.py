# -*- coding: utf-8 -*-
"""
core/sell_market.py 鈥?Execute a market sell order
Usage: python core/sell_market.py SYMBOL [QUANTITY | --all]
Example: python core/sell_market.py BTC 0.001
         python core/sell_market.py DRAMB --all
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


def sell_market(symbol: str, quantity: float = None, sell_all: bool = False):
    """Execute a market sell order."""
    sym = f"{symbol.upper()}/USDT"
    ex = create_exchange()

    # Get current holdings
    bal = ex.fetch_balance()
    coin_bal = bal.get(symbol.upper(), {})
    free_qty = float(coin_bal.get("free", 0) or 0)

    if free_qty <= 0:
        print(f"Error: No {symbol.upper()} available to sell (balance: {free_qty})")
        sys.exit(1)

    if sell_all:
        quantity = free_qty
    elif quantity is None or quantity <= 0:
        print(f"Error: Specify quantity or use --all")
        sys.exit(1)

    if quantity > free_qty:
        print(f"Error: Requested {quantity} but only {free_qty} available")
        sys.exit(1)

    # Precision
    mkt = ex.market(sym)
    ap = mkt.get("precision", {}).get("amount", 8)
    if isinstance(ap, int):
        quantity = math.floor(quantity * 10**ap) / 10**ap
    else:
        quantity = float(ex.amount_to_precision(sym, quantity))

    # Current price
    ticker = ex.fetch_ticker(sym)
    current_price = float(ticker["last"])
    est_value = quantity * current_price

    print(f"Current {symbol.upper()} price: ${current_price:,.2f}")
    print(f"Selling {quantity} {symbol.upper()} (~${est_value:.2f} USDT)...")

    order = ex.create_market_sell_order(sym, quantity)
    filled_price = float(order.get("average", 0) or order.get("price", 0) or current_price)
    filled_cost = float(order.get("cost", 0) or quantity * filled_price)
    filled_qty = float(order.get("filled", 0) or quantity)

    print(f"\n{'=' * 60}")
    print(f"  鉁?MARKET SELL COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Order ID:  {order.get('id', '?')}")
    print(f"  Status:    {order.get('status', '?')}")
    print(f"  Sold:      {filled_qty} {symbol.upper()}")
    print(f"  Avg Price: ${filled_price:,.2f}")
    print(f"  Received:  ${filled_cost:.2f} USDT")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sell_market.py SYMBOL [QUANTITY | --all]")
        print("Example: python sell_market.py BTC 0.001")
        print("         python sell_market.py DRAMB --all")
        sys.exit(1)

    symbol = sys.argv[1]
    sell_all = "--all" in sys.argv
    qty = None
    if not sell_all and len(sys.argv) >= 3:
        try:
            qty = float(sys.argv[2])
        except ValueError:
            pass

    sell_market(symbol, qty, sell_all)
