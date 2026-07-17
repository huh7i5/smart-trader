"""Analyze Binance taker buy/sell flow and visible order-book depth."""

from __future__ import annotations

import argparse
import json
import sys

import requests

from pre_trade_checklist import DEPTH_URL, KLINES_URL, fetch_json, retail_taker_flow
from trader_runtime import iso_utc, load_config, normalize_symbol, proxy_dict, state_dir, symbol_id, write_json_atomic


def analyze_symbol(session, symbol: str, hours: int, timeout: int, proxies) -> dict:
    normalized = normalize_symbol(symbol)
    raw_symbol = symbol_id(normalized)
    hourly = fetch_json(
        session,
        KLINES_URL,
        params={"symbol": raw_symbol, "interval": "1h", "limit": hours},
        timeout=timeout,
        proxies=proxies,
    )
    depth = fetch_json(
        session,
        DEPTH_URL,
        params={"symbol": raw_symbol, "limit": 100},
        timeout=timeout,
        proxies=proxies,
    )
    flow = retail_taker_flow(hourly)
    bid_notional = sum(float(price) * float(qty) for price, qty in depth.get("bids") or [])
    ask_notional = sum(float(price) * float(qty) for price, qty in depth.get("asks") or [])
    flow.update(
        {
            "symbol": normalized,
            "visible_bid_notional": round(bid_notional, 4),
            "visible_ask_notional": round(ask_notional, 4),
            "visible_bid_ask_ratio": round(bid_notional / ask_notional, 6) if ask_notional else None,
        }
    )
    return flow


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-backed Binance fund-flow proxy")
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--symbols", nargs="+", default=["BTC", "SOL", "LINK", "DOGE"])
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    config = load_config()
    proxies = proxy_dict(config)
    try:
        with requests.Session() as session:
            results = [
                analyze_symbol(session, symbol, max(2, min(args.hours, 168)), max(3, args.timeout), proxies)
                for symbol in args.symbols
            ]
    except (requests.RequestException, ValueError, KeyError) as exc:
        print(f"FLOW_DATA_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    report = {
        "schema_version": 1,
        "fetched_at_utc": iso_utc(),
        "hours": args.hours,
        "source": {"klines": KLINES_URL, "order_book": DEPTH_URL},
        "method": "Binance taker-buy base volume; sell volume = total volume - taker-buy volume",
        "results": results,
    }
    output = state_dir() / "latest_fund_flow.json"
    write_json_atomic(output, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"BINANCE TAKER FLOW | fetched={report['fetched_at_utc']} | hours={args.hours}")
        for row in results:
            print(
                f"{row['symbol']:<14} taker_buy={row['taker_buy_ratio']:.2%} "
                f"price={row['price_change_pct']:+.2f}% bid/ask={row['visible_bid_ask_ratio']}"
            )
        print(f"Evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
