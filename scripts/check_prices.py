# -*- coding: utf-8 -*-
"""
core/check_prices.py 鈥?Real-time price monitoring for tracked assets
Usage: python core/check_prices.py [SYMBOL1 SYMBOL2 ...]
Default symbols: BTC SOL LINK DOGE DRAMB NVDAB GOOGLB
"""
import sys, io, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ccxt

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_SYMBOLS = [
    "BTC/USDT", "SOL/USDT", "LINK/USDT", "DOGE/USDT",
    "DRAMB/USDT", "NVDAB/USDT", "GOOGLB/USDT",
]


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


def check_prices(symbols=None):
    """Fetch and display current prices for specified symbols."""
    if symbols is None:
        symbols = DEFAULT_SYMBOLS

    ex = create_exchange()

    print("=" * 60)
    print("  REAL-TIME PRICES")
    print("=" * 60)

    for sym in symbols:
        try:
            t = ex.fetch_ticker(sym)
            price = t["last"]
            pct = t.get("percentage", 0) or 0
            high = t.get("high", 0) or 0
            low = t.get("low", 0) or 0
            vol = t.get("baseVolume", 0) or 0
            print(f"  {sym:16s}: ${price:<12} (24h: {pct:+.2f}%)  H: ${high}  L: ${low}")
        except Exception as e:
            print(f"  {sym:16s}: ERROR - {e}")

    # Also show USDT balance
    bal = ex.fetch_balance()
    usdt_free = float(bal.get("USDT", {}).get("free", 0) or 0)
    usdt_locked = float(bal.get("USDT", {}).get("used", 0) or 0)
    print(f"\n  USDT: free=${usdt_free:.2f} | locked=${usdt_locked:.2f} | total=${usdt_free + usdt_locked:.2f}")


if __name__ == "__main__":
    custom_symbols = None
    if len(sys.argv) > 1:
        custom_symbols = [f"{s.upper()}/USDT" for s in sys.argv[1:]]
    check_prices(custom_symbols)
