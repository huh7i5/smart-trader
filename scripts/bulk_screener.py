import ccxt
import json
import pandas as pd
import numpy as np
import datetime
import concurrent.futures
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def load_config():
    try:
        cfg = json.load(open(r"d:\money\new222\config.json"))
        return cfg
    except Exception:
        return {}

def create_exchange():
    cfg = load_config()
    ex = ccxt.binance({
        "enableRateLimit": True,
        "timeout": 30000,
        "options": {"defaultType": "spot", "adjustForTimeDifference": True}
    })
    if cfg.get("proxy"):
        ex.proxies = {"http": cfg["proxy"], "https": cfg["proxy"]}
    return ex

def scan_symbol(ex, sym):
    try:
        # 1. Smart Money Check
        daily = ex.fetch_ohlcv(sym, timeframe="1d", limit=7)
        if len(daily) >= 7:
            week_ago_close = daily[0][4]
            current_close = daily[-1][4]
            weekly_change = (current_close - week_ago_close) / week_ago_close * 100
        else:
            weekly_change = 0.0

        ob = ex.fetch_order_book(sym, limit=20)
        total_bid = sum(b[0] * b[1] for b in ob["bids"])
        total_ask = sum(a[0] * a[1] for a in ob["asks"])
        bid_ask_ratio = total_bid / total_ask if total_ask > 0 else 0.0

        sm_pass = weekly_change > 0 and bid_ask_ratio > 1.0

        # 2. Retail Behavior Check (6h)
        klines = ex.fetch_ohlcv(sym, timeframe="1h", limit=6)
        total_buy = 0.0
        total_sell = 0.0
        for k in klines:
            o, h, l, c, vol = k[1], k[2], k[3], k[4], k[5]
            price_range = h - l
            buy_ratio = (c - l) / price_range if price_range > 0 else 0.5
            total_buy += vol * buy_ratio
            total_sell += vol * (1.0 - buy_ratio)

        net_flow = total_buy - total_sell
        is_net_buy = net_flow > 0

        if len(klines) >= 2:
            price_start = klines[0][1]
            price_end = klines[-1][4]
            price_change = (price_end - price_start) / price_start * 100
        else:
            price_change = 0.0

        retail_selling_price_stable = (not is_net_buy) and (price_change > -1.0)
        retail_pass = is_net_buy or retail_selling_price_stable

        return {
            'symbol': sym,
            'weekly_change': weekly_change,
            'bid_ask_ratio': bid_ask_ratio,
            'net_flow_6h': 'NET BUY' if is_net_buy else 'NET SELL',
            'price_change_6h': price_change,
            'sm_pass': sm_pass,
            'retail_pass': retail_pass,
            'all_pass': sm_pass and retail_pass,
            'error': None
        }
    except Exception as e:
        return {
            'symbol': sym,
            'error': str(e)
        }

def main():
    ex = create_exchange()
    ex.load_markets()

    cryptos = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
        'ADA/USDT', 'DOGE/USDT', 'SHIB/USDT', 'LINK/USDT', 'DOT/USDT', 
        'LTC/USDT', 'UNI/USDT', 'NEAR/USDT', 'SUI/USDT', 'APT/USDT', 
        'OP/USDT', 'ARB/USDT', 'AVAX/USDT', 'FIL/USDT', 'FET/USDT', 
        'ICP/USDT', 'LDO/USDT', 'TIA/USDT', 'PENDLE/USDT', 'FTM/USDT'
    ]

    # Full list of all 33 bStocks available on Binance
    b_stocks = [
        'AAOIB/USDT', 'AMDB/USDT', 'ARMB/USDT', 'AVGOB/USDT', 'BABAB/USDT', 
        'COINB/USDT', 'CRCLB/USDT', 'DRAMB/USDT', 'EWYB/USDT', 'GLWB/USDT', 
        'GOOGLB/USDT', 'HOODB/USDT', 'IBMB/USDT', 'INTCB/USDT', 'LITEB/USDT', 
        'METAB/USDT', 'MRVLB/USDT', 'MSFTB/USDT', 'MSTRB/USDT', 'MUB/USDT', 
        'NBISB/USDT', 'NOKB/USDT', 'NVDAB/USDT', 'PLTRB/USDT', 'QCOMB/USDT', 
        'QQQB/USDT', 'RKLBB/USDT', 'SOXLB/USDT', 'SPCXB/USDT', 'SPYB/USDT', 
        'TSLAB/USDT', 'TSMB/USDT', 'WDCB/USDT'
    ]

    all_symbols = cryptos + b_stocks
    print(f"Starting rigorous bulk scan for {len(all_symbols)} symbols ({len(cryptos)} Cryptos, {len(b_stocks)} bStocks)...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_sym = {executor.submit(scan_symbol, ex, sym): sym for sym in all_symbols}
        for future in concurrent.futures.as_completed(future_to_sym):
            sym = future_to_sym[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as exc:
                print(f"  {sym:<12} generated an exception: {exc}")

    print("\n" + "="*80)
    print("  📋 BULK SCAN RESULTS: FULLY GREEN (🟢🟢🟢) PASSED SYMBOLS")
    print("="*80)
    
    passed = [r for r in results if r.get('all_pass')]
    
    if not passed:
        print("  NO SYMBOLS PASSED THE CHECKLIST (0 / {} passed)".format(len(results)))
    else:
        print(f"{'Symbol':<12} | {'Asset Type':<10} | {'7d Trend':<10} | {'Bid/Ask Ratio':<13} | {'6h Net Flow':<11} | {'6h Price'}")
        print("-" * 80)
        for r in passed:
            is_bstock = r['symbol'].endswith("B/USDT")
            asset_type = "bStock" if is_bstock else "Crypto"
            print(f"{r['symbol']:<12} | {asset_type:<10} | {r['weekly_change']:+9.2f}% | {r['bid_ask_ratio']:12.2f}x | {r['net_flow_6h']:<11} | {r['price_change_6h']:+7.2f}%")
            
    print("="*80)

if __name__ == "__main__":
    main()
