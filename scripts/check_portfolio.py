"""Inspect the private Binance Spot account using the portable config path."""

from __future__ import annotations

import argparse
import json
import sys

from trader_runtime import create_exchange, iso_utc, state_dir, write_json_atomic


def build_portfolio(exchange) -> dict:
    balance = exchange.fetch_balance()
    open_orders = exchange.fetch_open_orders()
    holdings = []
    total_value = 0.0
    for asset, raw_amount in (balance.get("total") or {}).items():
        amount = float(raw_amount or 0)
        if amount <= 0 or asset == "USDT":
            continue
        symbol = f"{asset}/USDT"
        if symbol not in exchange.markets:
            holdings.append({"asset": asset, "quantity": amount, "price": None, "value_usdt": None})
            continue
        try:
            price = float(exchange.fetch_ticker(symbol)["last"])
            value = amount * price
            total_value += value
            holdings.append({"asset": asset, "quantity": amount, "price": price, "value_usdt": value})
        except Exception as exc:
            holdings.append(
                {"asset": asset, "quantity": amount, "price": None, "value_usdt": None, "error": str(exc)}
            )
    usdt = balance.get("USDT") or {}
    usdt_free = float(usdt.get("free", 0) or 0)
    usdt_used = float(usdt.get("used", 0) or 0)
    return {
        "fetched_at_utc": iso_utc(),
        "holdings": holdings,
        "open_orders": [
            {
                "id": str(order.get("id")),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "type": order.get("type"),
                "price": order.get("price"),
                "amount": order.get("amount"),
                "filled": order.get("filled"),
                "remaining": order.get("remaining"),
            }
            for order in open_orders
        ],
        "usdt": {"free": usdt_free, "locked": usdt_used, "total": usdt_free + usdt_used},
        "spot_holdings_value_usdt": total_value,
        "account_value_usdt": total_value + usdt_free + usdt_used,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Binance Spot portfolio")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = build_portfolio(create_exchange(private=True))
    except Exception as exc:
        print(f"PORTFOLIO_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    output = state_dir() / "latest_portfolio.json"
    write_json_atomic(output, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"PORTFOLIO | fetched={report['fetched_at_utc']}")
        for row in report["holdings"]:
            value = "unpriced" if row["value_usdt"] is None else f"{row['value_usdt']:.2f} USDT"
            print(f"{row['asset']:<10} qty={row['quantity']:<18.8g} value={value}")
        print(
            f"USDT free={report['usdt']['free']:.2f} locked={report['usdt']['locked']:.2f} | "
            f"account~{report['account_value_usdt']:.2f} USDT"
        )
        print(f"Open orders: {len(report['open_orders'])} | Evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
