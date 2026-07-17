"""Preview or execute a guarded Binance Spot market sell."""

from __future__ import annotations

import argparse
import sys

from order_safety import (
    SafetyError,
    assert_order_execution_enabled,
    consume_proposal,
    create_proposal,
    load_proposal,
    lock_proposal_for_submission,
)
from trader_runtime import ConfigurationError, create_exchange, load_config, normalize_symbol


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded market sell; previews by default")
    parser.add_argument("symbol")
    quantity_group = parser.add_mutually_exclusive_group(required=True)
    quantity_group.add_argument("--quantity", type=float)
    quantity_group.add_argument("--all", action="store_true", dest="sell_all")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    symbol = normalize_symbol(args.symbol)
    params = {"symbol": symbol, "quantity": args.quantity, "sell_all": args.sell_all}
    try:
        config = load_config(require_private=True)
        if args.sell_all and symbol in config.get("core_symbols", []) and not config.get("allow_core_full_sell"):
            raise SafetyError(
                "full sale of a core symbol is disabled; set allow_core_full_sell=true only after thesis review"
            )
        exchange = create_exchange(private=True)
        base = symbol.split("/")[0]
        balance = exchange.fetch_balance()
        free_quantity = float(balance.get(base, {}).get("free", 0) or 0)
        quantity = free_quantity if args.sell_all else float(args.quantity or 0)
        if quantity <= 0 or quantity > free_quantity:
            raise SafetyError(f"invalid quantity {quantity}; available {free_quantity}")
        quantity = float(exchange.amount_to_precision(symbol, quantity))
        price = float(exchange.fetch_ticker(symbol)["last"])
        params["resolved_quantity"] = quantity
        if not args.confirm:
            proposal = create_proposal(
                action="market_sell",
                params=params,
                checklist=None,
                snapshot={"free_quantity": free_quantity, "market_price": price, "estimated_value_usdt": quantity * price},
            )
            print("PREVIEW ONLY - NO ORDER SENT")
            print(f"Sell: {quantity} {base} near {price:,.8g} (~{quantity * price:.2f} USDT)")
            print(f"Proposal token: {proposal['token']}")
            print("Wait for explicit user confirmation before rerunning with --confirm TOKEN.")
            return 0
        proposal = load_proposal(args.confirm, action="market_sell", params=params)
        assert_order_execution_enabled()
        lock_proposal_for_submission(proposal)
        try:
            order = exchange.create_market_sell_order(symbol, quantity)
        except Exception as exc:
            print(
                f"ORDER_STATE_UNKNOWN: {exc}. Token locked; verify open orders and portfolio before any retry.",
                file=sys.stderr,
            )
            return 3
        consume_proposal(proposal, str(order.get("id")) if order.get("id") else None)
        print(f"MARKET SELL SUBMITTED | id={order.get('id')} | status={order.get('status')}")
        return 0
    except (SafetyError, ConfigurationError, ValueError, KeyError) as exc:
        print(f"ORDER_BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
