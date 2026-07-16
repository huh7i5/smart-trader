# -*- coding: utf-8 -*-
"""
core/check_portfolio.py 鈥?Check current holdings, P&L, and open orders (Optimized)
Usage: python core/check_portfolio.py
"""
import sys, io, json, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ccxt

CONFIG_PATH = Path(__file__).resolve().parent.parent / "new222" / "config.json"

# Tracked symbols to avoid requesting all 500+ Binance spot markets
SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "LINK/USDT", "DOGE/USDT",
    "DRAMB/USDT", "NVDAB/USDT", "GOOGLB/USDT", "QQQ/USDT",
    "BNB/USDT", "TRX/USDT", "XRP/USDT", "ZEC/USDT", "JST/USDT",
    "MORPHO/USDT", "DASH/USDT", "RENDER/USDT", "SUI/USDT",
    "MUB/USDT", "SNDKB/USDT"
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
            "fetchOpenOrders": {
                "warnWithoutSymbol": False,
            },
        },
    })
    if cfg.get("proxy"):
        ex.proxies = {"http": cfg["proxy"], "https": cfg["proxy"]}
    st = ex.fetch_time()
    lt = ex.milliseconds()
    ex.options["timeDifference"] = lt - st
    ex.load_markets()
    return ex

def check_portfolio():
    """Fetch and display full portfolio status."""
    ex = create_exchange()

    # 1. Open orders (pending)
    print("=" * 75)
    print("  OPEN ORDERS (still waiting)")
    print("=" * 75)
    all_open = []
    for sym in SYMBOLS:
        try:
            orders = ex.fetch_open_orders(sym)
            all_open.extend(orders)
            time.sleep(0.05)
        except Exception:
            pass

    if not all_open:
        print("  None! All orders filled or cancelled.")
    else:
        for o in all_open:
            sym = o.get("symbol", "")
            price = o.get("price", 0)
            amount = o.get("amount", 0)
            filled = o.get("filled", 0)
            remaining = o.get("remaining", 0)
            oid = o.get("id", "")
            print(f"  {sym:<14} limit={price:<12} qty={amount:<12} filled={filled} remaining={remaining}  id={oid}")

    # 2. Recently filled orders (last 48h)
    print(f"\n{'='*75}")
    print("  RECENTLY FILLED ORDERS (last 48h)")
    print(f"{'='*75}")
    since = ex.milliseconds() - 48 * 3600 * 1000
    filled_orders = []
    for sym in SYMBOLS:
        try:
            trades = ex.fetch_my_trades(sym, since=since)
            for t in trades:
                filled_orders.append(t)
            time.sleep(0.05)
        except Exception:
            pass

    if not filled_orders:
        print("  No recent fills found.")
    else:
        filled_orders.sort(key=lambda x: x.get("timestamp", 0))
        for t in filled_orders:
            sym = t.get("symbol", "")
            side = t.get("side", "")
            price = float(t.get("price", 0))
            amount = float(t.get("amount", 0))
            cost = float(t.get("cost", 0))
            dt = t.get("datetime", "")[:19]
            print(f"  {dt}  {sym:<14} {side:<5} price={price:<12} qty={amount:<14} cost={cost:.4f} USDT")

    # 3. Current holdings
    print(f"\n{'='*75}")
    print("  CURRENT HOLDINGS & VALUE")
    print(f"{'='*75}")
    bal = ex.fetch_balance()
    total_value = 0.0
    
    usdt_free = float(bal.get("USDT", {}).get("free", 0) or 0)
    usdt_locked = float(bal.get("USDT", {}).get("used", 0) or 0)
    usdt_total = usdt_free + usdt_locked

    for sym in SYMBOLS:
        base = sym.split("/")[0]
        amt = float(bal.get(base, {}).get("total", 0) or 0)
        if amt > 1e-8:
            try:
                tk = ex.fetch_ticker(sym)
                price = float(tk["last"])
                value = amt * price
                total_value += value
                print(f"  {base:8s} qty={amt:<18.6f} price={price:<14,.4f} value={value:.4f} USDT")
                time.sleep(0.05)
            except Exception:
                pass

    print()
    print(f"  USDT: free=${usdt_free:.2f} | locked(in orders)=${usdt_locked:.2f} | total=${usdt_total:.2f}")
    print(f"  Spot holdings value: {total_value:.2f} USDT")
    print(f"  Total account: ~{total_value + usdt_total:.2f} USDT")

if __name__ == "__main__":
    check_portfolio()
