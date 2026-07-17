"""Fetch public Binance prices without loading API credentials."""

from __future__ import annotations

import argparse
import json
import sys

from trader_runtime import create_exchange, iso_utc, normalize_symbol, state_dir, write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Check current Binance Spot prices")
    parser.add_argument("symbols", nargs="*", default=["BTC", "SOL", "LINK", "DOGE", "DRAMB", "NVDAB", "GOOGLB"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        exchange = create_exchange(private=False)
        rows = []
        for raw in args.symbols:
            symbol = normalize_symbol(raw)
            ticker = exchange.fetch_ticker(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "last": float(ticker["last"]),
                    "change_pct_24h": float(ticker.get("percentage") or 0),
                    "high_24h": float(ticker.get("high") or 0),
                    "low_24h": float(ticker.get("low") or 0),
                    "quote_volume_24h": float(ticker.get("quoteVolume") or 0),
                }
            )
    except Exception as exc:
        print(f"PRICE_DATA_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    report = {"fetched_at_utc": iso_utc(), "source": "Binance Spot public ticker", "results": rows}
    output = state_dir() / "latest_prices.json"
    write_json_atomic(output, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"BINANCE PRICES | fetched={report['fetched_at_utc']}")
        for row in rows:
            print(f"{row['symbol']:<14} {row['last']:>14,.8g}  24h={row['change_pct_24h']:+.2f}%")
        print(f"Evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
