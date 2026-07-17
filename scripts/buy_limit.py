"""Preview or execute a guarded Binance Spot limit buy."""

from __future__ import annotations

import argparse
import sys

from order_safety import (
    SafetyError,
    assert_order_execution_enabled,
    checklist_for_buy,
    consume_proposal,
    create_proposal,
    load_proposal,
    lock_proposal_for_submission,
    validate_buy_risk,
)
from trader_runtime import ConfigurationError, create_exchange, normalize_symbol
from buy_market import estimated_cost_basis


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded limit buy; previews by default")
    parser.add_argument("symbol")
    parser.add_argument("price", type=float)
    parser.add_argument("amount_usdt", type=float)
    parser.add_argument("--mode", choices=("active", "baseline"), default="active")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    symbol = normalize_symbol(args.symbol)
    if args.price <= 0:
        print("ORDER_BLOCKED: price must be positive", file=sys.stderr)
        return 2
    params = {
        "symbol": symbol,
        "price": args.price,
        "amount_usdt": args.amount_usdt,
        "mode": args.mode,
    }
    try:
        exchange = create_exchange(private=True)
        current = float(exchange.fetch_ticker(symbol)["last"])
        risk = validate_buy_risk(exchange, symbol, args.amount_usdt)
        checklist = checklist_for_buy(symbol, args.mode)
        base = symbol.split("/")[0]
        current_qty = float(exchange.fetch_balance().get(base, {}).get("total", 0) or 0)
        old_cost = estimated_cost_basis(exchange, symbol)
        projected_cost = (
            ((old_cost * current_qty) + args.amount_usdt)
            / (current_qty + args.amount_usdt / args.price)
            if old_cost is not None and current_qty > 0
            else args.price
        )
        if not args.confirm:
            proposal = create_proposal(
                action="limit_buy",
                params=params,
                checklist=checklist,
                snapshot={
                    **risk,
                    "market_price": current,
                    "estimated_current_cost": old_cost,
                    "projected_cost": projected_cost,
                },
            )
            print(f"Projected cost basis: {projected_cost:,.8g} (estimate from available trade history)")
            print("PREVIEW ONLY - NO ORDER SENT")
            print(
                f"Limit buy: {args.amount_usdt:.2f} USDT of {symbol} at {args.price:,.8g} "
                f"({(args.price / current - 1) * 100:+.2f}% vs market)"
            )
            print(f"USDT after order: {risk['usdt_after_order']:.2f}")
            print(f"Proposal token: {proposal['token']}")
            print("Wait for explicit user confirmation before rerunning with --confirm TOKEN.")
            return 0
        proposal = load_proposal(args.confirm, action="limit_buy", params=params)
        assert_order_execution_enabled()
        checklist_for_buy(symbol, args.mode)
        validate_buy_risk(exchange, symbol, args.amount_usdt)
        quantity = float(exchange.amount_to_precision(symbol, args.amount_usdt / args.price))
        price = float(exchange.price_to_precision(symbol, args.price))
        lock_proposal_for_submission(proposal)
        try:
            order = exchange.create_limit_buy_order(symbol, quantity, price)
        except Exception as exc:
            print(
                f"ORDER_STATE_UNKNOWN: {exc}. Token locked; verify open orders and portfolio before any retry.",
                file=sys.stderr,
            )
            return 3
        consume_proposal(proposal, str(order.get("id")) if order.get("id") else None)
        print(f"LIMIT BUY SUBMITTED | id={order.get('id')} | status={order.get('status')}")
        return 0
    except (SafetyError, ConfigurationError, ValueError, KeyError) as exc:
        print(f"ORDER_BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
