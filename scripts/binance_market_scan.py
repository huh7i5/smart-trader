"""Fetch verifiable Binance Spot rankings instead of asking an LLM to infer them."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests

from trader_runtime import iso_utc, load_config, proxy_dict, state_dir, write_json_atomic


EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
TICKER_24H_URL = "https://api.binance.com/api/v3/ticker/24hr"
PRODUCTS_URL = (
    "https://www.binance.com/bapi/asset/v2/public/asset-service/product/"
    "get-products?includeEtf=true"
)


class MarketDataError(RuntimeError):
    """Raised when Binance evidence cannot be fetched or validated."""


def fetch_json(session: requests.Session, url: str, *, timeout: int, proxies=None) -> Any:
    response = session.get(url, timeout=timeout, proxies=proxies)
    response.raise_for_status()
    payload = response.json()
    if payload is None:
        raise MarketDataError(f"Empty JSON response from {url}")
    return payload


def build_rankings(
    exchange_info: dict[str, Any],
    tickers: list[dict[str, Any]],
    products_payload: dict[str, Any],
    *,
    category: str,
    quote: str,
    limit: int,
    min_quote_volume: float,
) -> dict[str, Any]:
    product_rows = products_payload.get("data") or []
    tags_by_symbol = {
        row.get("s"): set(row.get("tags") or [])
        for row in product_rows
        if isinstance(row, dict) and row.get("s")
    }
    trading = {
        row["symbol"]: row
        for row in exchange_info.get("symbols") or []
        if row.get("status") == "TRADING"
        and row.get("isSpotTradingAllowed", True)
        and row.get("quoteAsset") == quote
    }

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        symbol = ticker.get("symbol")
        market = trading.get(symbol)
        if not market:
            continue
        tags = tags_by_symbol.get(symbol, set())
        is_bstock = "bStocks" in tags
        if category == "bstock" and not is_bstock:
            continue
        if category == "crypto" and is_bstock:
            continue
        try:
            quote_volume = float(ticker.get("quoteVolume") or 0)
            row = {
                "symbol": symbol,
                "display_symbol": f"{market['baseAsset']}/{market['quoteAsset']}",
                "asset_type": "bstock" if is_bstock else "crypto",
                "last_price": float(ticker.get("lastPrice") or 0),
                "price_change_pct_24h": float(ticker.get("priceChangePercent") or 0),
                "quote_volume_24h": quote_volume,
                "trade_count_24h": int(ticker.get("count") or 0),
                "tags": sorted(tags),
            }
        except (TypeError, ValueError, KeyError):
            continue
        if row["last_price"] <= 0 or quote_volume < min_quote_volume:
            continue
        rows.append(row)

    if not rows:
        raise MarketDataError(
            f"Binance returned zero eligible {category} {quote} markets; do not invent rankings"
        )

    return {
        "market_count": len(rows),
        "gainers": sorted(rows, key=lambda item: item["price_change_pct_24h"], reverse=True)[:limit],
        "losers": sorted(rows, key=lambda item: item["price_change_pct_24h"])[:limit],
        "volume": sorted(rows, key=lambda item: item["quote_volume_24h"], reverse=True)[:limit],
    }


def scan_markets(
    *, category: str = "all", quote: str = "USDT", limit: int = 10,
    min_quote_volume: float = 0, timeout: int = 20,
) -> dict[str, Any]:
    config = load_config()
    proxies = proxy_dict(config)
    with requests.Session() as session:
        exchange_info = fetch_json(session, EXCHANGE_INFO_URL, timeout=timeout, proxies=proxies)
        tickers = fetch_json(session, TICKER_24H_URL, timeout=timeout, proxies=proxies)
        products = fetch_json(session, PRODUCTS_URL, timeout=timeout, proxies=proxies)
    if not isinstance(tickers, list) or not isinstance(products, dict):
        raise MarketDataError("Unexpected Binance response schema; do not invent rankings")
    if products.get("code") != "000000" or not isinstance(products.get("data"), list) or not products["data"]:
        raise MarketDataError("Binance product tags are unavailable; do not guess bStock classification")

    rankings = build_rankings(
        exchange_info,
        tickers,
        products,
        category=category,
        quote=quote,
        limit=limit,
        min_quote_volume=min_quote_volume,
    )
    return {
        "schema_version": 1,
        "status": "ok",
        "fetched_at_utc": iso_utc(),
        "category": category,
        "quote_asset": quote,
        "minimum_quote_volume_24h": min_quote_volume,
        "source": {
            "exchange_info": EXCHANGE_INFO_URL,
            "ticker_24h": TICKER_24H_URL,
            "product_tags": PRODUCTS_URL,
        },
        **rankings,
    }


def print_table(report: dict[str, Any]) -> None:
    print(
        f"BINANCE LIVE RANKINGS | {report['category']} | fetched={report['fetched_at_utc']} | "
        f"markets={report['market_count']}"
    )
    for section in ("gainers", "losers", "volume"):
        print(f"\n{section.upper()}")
        for index, row in enumerate(report[section], 1):
            print(
                f"{index:>2}. {row['display_symbol']:<14} "
                f"change={row['price_change_pct_24h']:+8.2f}% "
                f"volume={row['quote_volume_24h']:>14,.2f} {report['quote_asset']} "
                f"last={row['last_price']:,.8g}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch evidence-backed Binance Spot rankings")
    parser.add_argument("--category", choices=("all", "crypto", "bstock"), default="all")
    parser.add_argument("--quote", default="USDT")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-volume", type=float, default=0)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    parser.add_argument("--output", type=Path, help="Also write the report to this path")
    args = parser.parse_args()

    try:
        report = scan_markets(
            category=args.category,
            quote=args.quote.upper(),
            limit=max(1, min(args.limit, 100)),
            min_quote_volume=max(0, args.min_volume),
            timeout=max(3, args.timeout),
        )
    except (MarketDataError, requests.RequestException, ValueError) as exc:
        print(f"DATA_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2

    latest_path = state_dir() / f"latest_market_scan_{args.category}.json"
    write_json_atomic(latest_path, report)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_table(report)
        print(f"\nEvidence: {latest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
