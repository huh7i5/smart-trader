"""Backward-compatible entry point for the dynamic Binance market scanner."""

from __future__ import annotations

import argparse
import json
import sys

import requests

from binance_market_scan import MarketDataError, print_table, scan_markets
from trader_runtime import state_dir, write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dynamically discover and rank Binance markets; does not claim a 3-point verdict"
    )
    parser.add_argument("--category", choices=("bstock", "crypto", "all"), default="bstock")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-volume", type=float, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = scan_markets(
            category=args.category,
            limit=max(1, min(args.limit, 100)),
            min_quote_volume=max(0, args.min_volume),
        )
    except (MarketDataError, requests.RequestException, ValueError) as exc:
        print(f"DATA_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    report["decision_ready"] = False
    report["warning"] = "Ranking evidence only. Macro/news is not checked, so this is not a trade verdict."
    output = state_dir() / f"latest_bulk_scan_{args.category}.json"
    write_json_atomic(output, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_table(report)
        print(f"\nNOT A TRADE VERDICT: {report['warning']}")
        print(f"Evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
