# -*- coding: utf-8 -*-
"""
core/cancel_order.py 鈥?Cancel open orders
Usage: python core/cancel_order.py ORDER_ID SYMBOL
       python core/cancel_order.py --all           (cancel all open orders)
Example: python core/cancel_order.py 64333741291 BTC/USDT
"""
import sys, io, json
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


def cancel_order(order_id: str, symbol: str):
    """Cancel a specific order."""
    ex = create_exchange()
    sym = symbol if "/" in symbol else f"{symbol.upper()}/USDT"

    print(f"Cancelling order {order_id} for {sym}...")
    result = ex.cancel_order(order_id, sym)

    print(f"\n{'=' * 60}")
    print(f"  鉁?ORDER CANCELLED")
    print(f"{'=' * 60}")
    print(f"  Order ID: {order_id}")
    print(f"  Symbol:   {sym}")
    print(f"  Status:   {result.get('status', 'cancelled')}")
    print(f"{'=' * 60}")


def cancel_all_orders():
    """Cancel all open orders."""
    ex = create_exchange()
    open_orders = ex.fetch_open_orders()

    if not open_orders:
        print("No open orders to cancel.")
        return

    print(f"Found {len(open_orders)} open order(s). Cancelling...")
    for o in open_orders:
        try:
            ex.cancel_order(o["id"], o["symbol"])
            print(f"  鉁?Cancelled: {o['symbol']} {o['side']} @ {o.get('price', '?')} (ID: {o['id']})")
        except Exception as e:
            print(f"  鉂?Failed to cancel {o['id']}: {e}")

    print(f"\nDone. Cancelled {len(open_orders)} order(s).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cancel_order.py ORDER_ID SYMBOL")
        print("       python cancel_order.py --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        cancel_all_orders()
    elif len(sys.argv) >= 3:
        cancel_order(sys.argv[1], sys.argv[2])
    else:
        print("Error: Specify ORDER_ID and SYMBOL, or use --all")
        sys.exit(1)
