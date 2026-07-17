"""Preview or execute guarded cancellation of Binance Spot orders."""

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
from trader_runtime import ConfigurationError, create_exchange, normalize_symbol


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded order cancellation; previews by default")
    parser.add_argument("--order-id")
    parser.add_argument("--symbol")
    parser.add_argument("--all", action="store_true", dest="cancel_all")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    if not args.cancel_all and (not args.order_id or not args.symbol):
        parser.error("provide --order-id and --symbol, or use --all")
    symbol = normalize_symbol(args.symbol) if args.symbol else None
    params = {"order_id": args.order_id, "symbol": symbol, "cancel_all": args.cancel_all}
    try:
        exchange = create_exchange(private=True)
        open_orders = exchange.fetch_open_orders(symbol) if symbol else exchange.fetch_open_orders()
        targets = open_orders if args.cancel_all else [
            order for order in open_orders if str(order.get("id")) == str(args.order_id)
        ]
        if not targets:
            raise SafetyError("no matching open orders")
        target_summary = [
            {"id": str(order.get("id")), "symbol": order.get("symbol"), "side": order.get("side"), "price": order.get("price")}
            for order in targets
        ]
        params["targets"] = target_summary
        if not args.confirm:
            proposal = create_proposal(
                action="cancel_orders",
                params=params,
                checklist=None,
                snapshot={"target_count": len(targets)},
            )
            print("PREVIEW ONLY - NO ORDERS CANCELLED")
            for target in target_summary:
                print(f"  {target['id']} {target['symbol']} {target['side']} @ {target['price']}")
            print(f"Proposal token: {proposal['token']}")
            print("Wait for explicit user confirmation before rerunning with --confirm TOKEN.")
            return 0
        proposal = load_proposal(args.confirm, action="cancel_orders", params=params)
        assert_order_execution_enabled()
        lock_proposal_for_submission(proposal)
        try:
            for order in targets:
                exchange.cancel_order(order["id"], order["symbol"])
        except Exception as exc:
            print(
                f"CANCEL_STATE_UNKNOWN: {exc}. Token locked; refresh open orders before any retry.",
                file=sys.stderr,
            )
            return 3
        consume_proposal(proposal, None)
        print(f"CANCELLED {len(targets)} ORDER(S)")
        return 0
    except (SafetyError, ConfigurationError, ValueError, KeyError) as exc:
        print(f"CANCEL_BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
