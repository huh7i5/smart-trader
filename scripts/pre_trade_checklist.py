"""Evidence-backed three-point pre-trade checklist.

This script uses Binance public market data and a separately verified macro/news
evidence file. Missing or stale data fails closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests

from macro_evidence import evidence_path, validate_evidence
from trader_runtime import (
    iso_utc,
    load_config,
    normalize_symbol,
    proxy_dict,
    read_json,
    state_dir,
    symbol_id,
    write_json_atomic,
)


KLINES_URL = "https://api.binance.com/api/v3/klines"
DEPTH_URL = "https://api.binance.com/api/v3/depth"


class ChecklistDataError(RuntimeError):
    """Raised when required live evidence is missing or malformed."""


def fetch_json(session: requests.Session, url: str, *, params: dict[str, Any], timeout: int, proxies=None):
    response = session.get(url, params=params, timeout=timeout, proxies=proxies)
    response.raise_for_status()
    return response.json()


def smart_money_proxy(daily: list[list[Any]], depth: dict[str, Any]) -> dict[str, Any]:
    """Measure trend and visible order-book imbalance; do not label it institutional flow."""
    if len(daily) < 7:
        raise ChecklistDataError("fewer than seven daily candles")
    start_close = float(daily[0][4])
    end_close = float(daily[-1][4])
    weekly_change = (end_close - start_close) / start_close * 100
    bids = depth.get("bids") or []
    asks = depth.get("asks") or []
    if not bids or not asks:
        raise ChecklistDataError("empty Binance order book")
    bid_notional = sum(float(price) * float(qty) for price, qty in bids)
    ask_notional = sum(float(price) * float(qty) for price, qty in asks)
    ratio = bid_notional / ask_notional if ask_notional > 0 else 0.0
    passed = weekly_change > 0 and ratio > 1.0
    return {
        "name": "market_structure_proxy",
        "status": "pass" if passed else "caution",
        "passed": passed,
        "weekly_change_pct": round(weekly_change, 4),
        "visible_bid_ask_notional_ratio": round(ratio, 4),
        "limitations": (
            "This is a price/order-book proxy, not ETF flow, whale holdings, or proof of smart-money activity."
        ),
    }


def retail_taker_flow(hourly: list[list[Any]]) -> dict[str, Any]:
    """Use Binance's real taker-buy volume field rather than candle-shape estimation."""
    if len(hourly) < 2:
        raise ChecklistDataError("fewer than two hourly candles")
    total_volume = sum(float(row[5]) for row in hourly)
    taker_buy = sum(float(row[9]) for row in hourly)
    if total_volume <= 0:
        raise ChecklistDataError("zero hourly trading volume")
    taker_sell = max(0.0, total_volume - taker_buy)
    buy_ratio = taker_buy / total_volume
    start_price = float(hourly[0][1])
    end_price = float(hourly[-1][4])
    price_change = (end_price - start_price) / start_price * 100
    selling_but_stable = taker_buy <= taker_sell and price_change > -1.0
    passed = buy_ratio >= 0.5 or selling_but_stable
    return {
        "name": "retail_taker_flow",
        "status": "pass" if passed else "caution",
        "passed": passed,
        "taker_buy_ratio": round(buy_ratio, 6),
        "taker_buy_base_volume": round(taker_buy, 8),
        "taker_sell_base_volume": round(taker_sell, 8),
        "price_change_pct": round(price_change, 4),
        "selling_but_price_stable": selling_but_stable,
    }


def macro_check(symbol: str, config: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    target = path or evidence_path(symbol)
    if not target.exists():
        return {
            "name": "macro_and_news",
            "status": "unknown",
            "passed": False,
            "reason": f"No verified evidence file at {target}",
            "evidence_path": str(target),
        }
    try:
        payload = read_json(target)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "name": "macro_and_news",
            "status": "unknown",
            "passed": False,
            "reason": f"Cannot read evidence: {exc}",
            "evidence_path": str(target),
        }
    valid, reason = validate_evidence(
        payload,
        symbol=symbol,
        max_age_hours=float(config.get("macro_evidence_ttl_hours", 6)),
    )
    status = payload.get("status", "unknown") if valid else "unknown"
    return {
        "name": "macro_and_news",
        "status": status,
        "passed": valid and status == "clear",
        "reason": reason,
        "checked_at_utc": payload.get("checked_at_utc"),
        "sources": payload.get("sources", []),
        "note": payload.get("note", ""),
        "evidence_path": str(target),
    }


def run_checklist(symbol: str, *, evidence: Path | None = None, timeout: int = 20) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    api_symbol = symbol_id(normalized)
    config = load_config()
    proxies = proxy_dict(config)
    with requests.Session() as session:
        daily = fetch_json(
            session,
            KLINES_URL,
            params={"symbol": api_symbol, "interval": "1d", "limit": 8},
            timeout=timeout,
            proxies=proxies,
        )
        hourly = fetch_json(
            session,
            KLINES_URL,
            params={"symbol": api_symbol, "interval": "1h", "limit": 6},
            timeout=timeout,
            proxies=proxies,
        )
        depth = fetch_json(
            session,
            DEPTH_URL,
            params={"symbol": api_symbol, "limit": 100},
            timeout=timeout,
            proxies=proxies,
        )

    checks = [smart_money_proxy(daily, depth), retail_taker_flow(hourly), macro_check(normalized, config, evidence)]
    all_pass = all(check["passed"] for check in checks)
    return {
        "schema_version": 1,
        "symbol": normalized,
        "checked_at_utc": iso_utc(),
        "all_pass": all_pass,
        "verdict": "trade_allowed" if all_pass else "do_not_trade",
        "checks": checks,
        "source": {
            "klines": KLINES_URL,
            "order_book": DEPTH_URL,
            "macro_news": "URL-backed local evidence; missing evidence fails closed",
        },
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"PRE-TRADE CHECKLIST | {report['symbol']} | {report['checked_at_utc']}")
    for check in report["checks"]:
        print(f"  {check['name']:<24} {check['status'].upper():<8} passed={check['passed']}")
    print(f"VERDICT: {report['verdict'].upper()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-backed pre-trade checklist")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--macro-evidence", type=Path)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = run_checklist(
            args.symbol,
            evidence=args.macro_evidence.resolve() if args.macro_evidence else None,
            timeout=max(3, args.timeout),
        )
    except (ChecklistDataError, requests.RequestException, ValueError) as exc:
        print(f"CHECKLIST_UNAVAILABLE: {exc}", file=sys.stderr)
        return 3

    stamp = report["checked_at_utc"].replace(":", "").replace("-", "")
    archived = state_dir() / f"checklist_{symbol_id(args.symbol)}_{stamp}.json"
    latest = state_dir() / f"latest_checklist_{symbol_id(args.symbol)}.json"
    write_json_atomic(archived, report)
    write_json_atomic(latest, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
        print(f"Evidence: {latest}")
    return 0 if report["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
